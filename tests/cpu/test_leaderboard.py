"""CPU acceptance tests for the bounded Wave-A fixture leaderboard."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import math
import os
import pickle
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from carbon import leaderboard
from carbon.fees import SubmissionId
from carbon.leaderboard import (
    FixtureLeaderboardCandidate,
    FixtureLeaderboardCandidateSnapshot,
    FixtureLeaderboardPage,
    FixtureLeaderboardProvider,
    FixtureLeaderboardResourceLimits,
    FixtureLeaderboardRow,
    FixtureLeaderboardService,
    LeaderboardCursor,
    LeaderboardError,
    LeaderboardIntegrationError,
    LeaderboardRequestError,
    LeaderboardResourceError,
    LeaderboardSnapshotSequence,
    LeaderboardUnavailableError,
    ListFixtureLeaderboardRequest,
    PublicationSequence,
)
from carbon.registry import ChallengeKey
from carbon.scoring import ScoreStatus

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEADERBOARD_ROOT = REPOSITORY_ROOT / "carbon" / "leaderboard"
U64_MAX = (1 << 64) - 1
CHALLENGE_KEY = ChallengeKey("a10_fixture", "fixture-1.0")
OTHER_CHALLENGE_KEY = ChallengeKey("other_fixture", "fixture-1.0")
SCORING_PACK_HASH = "sha256:" + "a" * 64
OTHER_SCORING_PACK_HASH = "sha256:" + "b" * 64
PUBLIC_EXPORTS = (
    "PublicationSequence",
    "LeaderboardSnapshotSequence",
    "LeaderboardCursor",
    "ListFixtureLeaderboardRequest",
    "FixtureLeaderboardCandidate",
    "FixtureLeaderboardCandidateSnapshot",
    "FixtureLeaderboardRow",
    "FixtureLeaderboardPage",
    "FixtureLeaderboardResourceLimits",
    "FixtureLeaderboardProvider",
    "FixtureLeaderboardService",
    "LeaderboardError",
    "LeaderboardRequestError",
    "LeaderboardResourceError",
    "LeaderboardUnavailableError",
    "LeaderboardIntegrationError",
)
MODEL_FIELDS = {
    PublicationSequence: ("value",),
    LeaderboardSnapshotSequence: ("value",),
    LeaderboardCursor: ("value",),
    ListFixtureLeaderboardRequest: ("challenge_key", "page_size", "cursor"),
    FixtureLeaderboardCandidate: (
        "submission_id",
        "result_id",
        "challenge_key",
        "scoring_pack_hash",
        "score_status",
        "overall_score",
        "mandatory_gates_passed",
        "fixture_origin",
        "eligible_for_emission",
        "publication_sequence",
    ),
    FixtureLeaderboardCandidateSnapshot: (
        "challenge_key",
        "scoring_pack_hash",
        "snapshot_sequence",
        "candidates",
    ),
    FixtureLeaderboardRow: (
        "rank",
        "challenge_key",
        "scoring_pack_hash",
        "overall_score",
        "mandatory_gates_passed",
        "publication_sequence",
        "fixture_origin",
        "eligible_for_emission",
    ),
    FixtureLeaderboardPage: (
        "schema_version",
        "challenge_key",
        "scoring_pack_hash",
        "snapshot_sequence",
        "rows",
        "next_cursor",
        "fixture_origin",
        "eligible_for_emission",
    ),
    FixtureLeaderboardResourceLimits: (
        "max_page_size",
        "max_snapshot_rows",
        "max_cursor_utf8_bytes",
        "max_string_utf8_bytes",
        "max_response_utf8_bytes",
        "max_concurrent_calls",
    ),
}
ERRORS = (
    (
        LeaderboardRequestError,
        "leaderboard.request.invalid",
        "Leaderboard request is invalid.",
    ),
    (
        LeaderboardResourceError,
        "leaderboard.resource.exhausted",
        "Leaderboard resource limit was exceeded.",
    ),
    (
        LeaderboardUnavailableError,
        "leaderboard.fixture.unavailable",
        "Fixture leaderboard is unavailable.",
    ),
    (
        LeaderboardIntegrationError,
        "leaderboard.integration.failed",
        "Leaderboard provider response is invalid.",
    ),
)


class _IntegerSubclass(int):
    pass


class _FloatSubclass(float):
    pass


class _StringSubclass(str):
    pass


class _TupleSubclass(tuple):
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


class _Provider:
    """Test-only retained fixture snapshot provider."""

    def __init__(
        self,
        value: FixtureLeaderboardCandidateSnapshot | None,
        *,
        failure: BaseException | None = None,
    ) -> None:
        self.value = value
        self.failure = failure
        self.calls: list[tuple[ChallengeKey, LeaderboardSnapshotSequence | None]] = []

    def get_snapshot(
        self,
        challenge_key: ChallengeKey,
        snapshot_sequence: LeaderboardSnapshotSequence | None,
    ) -> FixtureLeaderboardCandidateSnapshot | None:
        self.calls.append((challenge_key, snapshot_sequence))
        if self.failure is not None:
            raise self.failure
        return self.value


def _submission_id(index: int) -> SubmissionId:
    return SubmissionId(f"00000000-0000-4000-8000-{index:012x}")


def _limits(**overrides: object) -> FixtureLeaderboardResourceLimits:
    values: dict[str, object] = {
        "max_page_size": 64,
        "max_snapshot_rows": 128,
        "max_cursor_utf8_bytes": 4096,
        "max_string_utf8_bytes": 4096,
        "max_response_utf8_bytes": 65536,
        "max_concurrent_calls": 4,
    }
    values.update(overrides)
    return FixtureLeaderboardResourceLimits(**values)  # type: ignore[arg-type]


def _candidate(
    index: int = 1,
    *,
    submission_id: SubmissionId | None = None,
    result_id: str | None = None,
    challenge_key: ChallengeKey = CHALLENGE_KEY,
    scoring_pack_hash: str = SCORING_PACK_HASH,
    score_status: ScoreStatus = ScoreStatus.SCORED,
    overall_score: float = 0.5,
    mandatory_gates_passed: bool = True,
    fixture_origin: bool = True,
    eligible_for_emission: bool = False,
    publication_sequence: PublicationSequence | None = None,
) -> FixtureLeaderboardCandidate:
    return FixtureLeaderboardCandidate(
        _submission_id(index) if submission_id is None else submission_id,
        f"result-{index}" if result_id is None else result_id,
        challenge_key,
        scoring_pack_hash,
        score_status,
        overall_score,
        mandatory_gates_passed,
        fixture_origin,
        eligible_for_emission,
        (
            PublicationSequence(index)
            if publication_sequence is None
            else publication_sequence
        ),
    )


def _snapshot(
    candidates: tuple[FixtureLeaderboardCandidate, ...] = (),
    *,
    challenge_key: ChallengeKey = CHALLENGE_KEY,
    scoring_pack_hash: str = SCORING_PACK_HASH,
    sequence: int = 17,
) -> FixtureLeaderboardCandidateSnapshot:
    return FixtureLeaderboardCandidateSnapshot(
        challenge_key,
        scoring_pack_hash,
        LeaderboardSnapshotSequence(sequence),
        candidates,
    )


def _request(
    *,
    challenge_key: ChallengeKey = CHALLENGE_KEY,
    page_size: int = 10,
    cursor: LeaderboardCursor | None = None,
) -> ListFixtureLeaderboardRequest:
    return ListFixtureLeaderboardRequest(challenge_key, page_size, cursor)


def _service(
    provider: object,
    *,
    limits: FixtureLeaderboardResourceLimits | None = None,
) -> FixtureLeaderboardService:
    return FixtureLeaderboardService(  # type: ignore[arg-type]
        provider, limits or _limits()
    )


def _forge(model_type: type[Any], **fields: object) -> Any:
    value = object.__new__(model_type)
    for name, field_value in fields.items():
        object.__setattr__(value, name, field_value)
    return value


def _forged_candidate(
    candidate: FixtureLeaderboardCandidate, **changes: object
) -> FixtureLeaderboardCandidate:
    values = {
        field.name: object.__getattribute__(candidate, field.name)
        for field in dataclasses.fields(FixtureLeaderboardCandidate)
    }
    values.update(changes)
    return _forge(FixtureLeaderboardCandidate, **values)


def _forged_snapshot(
    snapshot: FixtureLeaderboardCandidateSnapshot, **changes: object
) -> FixtureLeaderboardCandidateSnapshot:
    values = {
        field.name: object.__getattribute__(snapshot, field.name)
        for field in dataclasses.fields(FixtureLeaderboardCandidateSnapshot)
    }
    values.update(changes)
    return _forge(FixtureLeaderboardCandidateSnapshot, **values)


def _response_utf8_bytes(page: FixtureLeaderboardPage) -> int:
    total = len(page.schema_version.encode("utf-8"))
    total += len(page.challenge_key.challenge_id.encode("utf-8"))
    total += len(page.challenge_key.version.encode("utf-8"))
    total += len(page.scoring_pack_hash.encode("utf-8"))
    for row in page.rows:
        total += len(row.challenge_key.challenge_id.encode("utf-8"))
        total += len(row.challenge_key.version.encode("utf-8"))
        total += len(row.scoring_pack_hash.encode("utf-8"))
    if page.next_cursor is not None:
        total += len(page.next_cursor.value.encode("utf-8"))
    return total


def _assert_fixed_identifier_error(
    error: LeaderboardError,
    identifier: str,
    expected_type: type[LeaderboardError],
) -> None:
    assert type(error) is expected_type
    assert identifier not in str(error)
    assert identifier not in repr(error)
    assert identifier not in error.args
    assert identifier not in error.__dict__.values()
    assert error.__cause__ is None
    assert error.__context__ is None


def _reachable_values(value: object) -> tuple[object, ...]:
    pending = [value]
    seen: set[int] = set()
    reached: list[object] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        reached.append(current)
        if type(current) is tuple:
            pending.extend(current)
        elif dataclasses.is_dataclass(current) and not isinstance(current, type):
            pending.extend(
                object.__getattribute__(current, field.name)
                for field in dataclasses.fields(type(current))
            )
    return tuple(reached)


def _valid_page(
    *, page_size: int = 10
) -> tuple[FixtureLeaderboardPage, _Provider, FixtureLeaderboardService]:
    candidates = (
        _candidate(1, overall_score=0.75),
        _candidate(2, overall_score=0.5),
    )
    provider = _Provider(_snapshot(candidates))
    service = _service(provider)
    return service.list_entries(_request(page_size=page_size)), provider, service


def test_exact_package_exports_fields_and_root_namespace() -> None:
    assert leaderboard.__all__ == PUBLIC_EXPORTS
    assert (
        tuple(name for name in vars(leaderboard) if not name.startswith("_"))
        == PUBLIC_EXPORTS
    )
    assert tuple(
        path.relative_to(LEADERBOARD_ROOT).as_posix()
        for path in sorted(LEADERBOARD_ROOT.glob("*.py"))
    ) == ("__init__.py", "model.py", "providers.py", "service.py")
    for model_type, expected_fields in MODEL_FIELDS.items():
        assert tuple(field.name for field in dataclasses.fields(model_type)) == (
            expected_fields
        )


def test_nominal_values_are_frozen_slotted_and_have_no_instance_dictionary() -> None:
    values = (
        PublicationSequence(0),
        LeaderboardSnapshotSequence(U64_MAX),
        LeaderboardCursor("ascii"),
        _request(),
        _candidate(),
        _snapshot((_candidate(),)),
        _limits(),
    )
    page, _, _ = _valid_page()
    values += (page.rows[0], page)
    for value in values:
        assert not hasattr(value, "__dict__")
        first_field = dataclasses.fields(value)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(value, first_field, None)


def test_nominal_values_reject_generic_pickle_serialization() -> None:
    page, _, _ = _valid_page()
    values = (
        PublicationSequence(0),
        LeaderboardSnapshotSequence(0),
        LeaderboardCursor("opaque"),
        _request(),
        _candidate(),
        _snapshot(),
        page.rows[0],
        page,
        _limits(),
    )
    for value in values:
        with pytest.raises(TypeError):
            pickle.dumps(value)


@pytest.mark.parametrize(("error_type", "code", "message"), ERRORS)
def test_error_hierarchy_and_fixed_nonserializable_payloads(
    error_type: type[LeaderboardError], code: str, message: str
) -> None:
    error = error_type()
    assert error_type.__bases__ == (LeaderboardError,)
    assert type(error) is error_type
    assert error.code == code
    assert error.message == message
    assert str(error) == message
    assert error.args == (message,)
    with pytest.raises(TypeError):
        error_type("private diagnostic")  # type: ignore[call-arg]
    with pytest.raises(AttributeError):
        error.code = "changed"  # type: ignore[misc]
    error.__dict__["code"] = "shadowed"
    error.__dict__["message"] = "shadowed"
    assert error.code == code and error.message == message
    with pytest.raises(TypeError):
        pickle.dumps(error)


def test_error_base_is_the_only_additional_exception_type() -> None:
    assert LeaderboardError.__bases__ == (Exception,)
    error_classes = tuple(
        value
        for value in vars(leaderboard).values()
        if inspect.isclass(value)
        and issubclass(value, Exception)
        and value.__module__.startswith("carbon.leaderboard")
    )
    assert set(error_classes) == {
        LeaderboardError,
        LeaderboardRequestError,
        LeaderboardResourceError,
        LeaderboardUnavailableError,
        LeaderboardIntegrationError,
    }


def test_protocol_is_structural_and_not_runtime_checkable() -> None:
    class StructuralProvider:
        def get_snapshot(
            self,
            challenge_key: ChallengeKey,
            snapshot_sequence: LeaderboardSnapshotSequence | None,
        ) -> FixtureLeaderboardCandidateSnapshot | None:
            del challenge_key, snapshot_sequence
            return _snapshot()

    concrete = StructuralProvider()
    service = FixtureLeaderboardService(concrete, _limits())
    assert service.list_entries(_request()).rows == ()
    with pytest.raises(TypeError):
        isinstance(concrete, FixtureLeaderboardProvider)


def test_service_constructor_signature_and_only_public_operation() -> None:
    assert tuple(inspect.signature(FixtureLeaderboardService).parameters) == (
        "provider",
        "resource_limits",
    )
    parameters = inspect.signature(FixtureLeaderboardService.list_entries).parameters
    assert tuple(parameters) == ("self", "request")
    public_members = tuple(
        name
        for name, value in vars(FixtureLeaderboardService).items()
        if not name.startswith("_") and callable(value)
    )
    assert public_members == ("list_entries",)
    for forbidden in (
        "get",
        "list_all",
        "get_by_submission",
        "global_rank",
        "official",
        "refresh",
        "serialize",
    ):
        assert not hasattr(FixtureLeaderboardService, forbidden)
    with pytest.raises(TypeError):
        FixtureLeaderboardService()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        FixtureLeaderboardService(_Provider(_snapshot()))  # type: ignore[call-arg]
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardService(None, _limits())  # type: ignore[arg-type]

    class ServiceSubclass(FixtureLeaderboardService):
        pass

    with pytest.raises(LeaderboardRequestError):
        ServiceSubclass(_Provider(_snapshot()), _limits())


def test_constructor_does_not_introspect_or_invoke_provider() -> None:
    class DeferredHostileProvider:
        @property
        def get_snapshot(self) -> object:
            raise AssertionError("provider inspected during construction")

    service = FixtureLeaderboardService(DeferredHostileProvider(), _limits())
    with pytest.raises(LeaderboardIntegrationError):
        service.list_entries(_request())


@pytest.mark.parametrize(
    "invalid",
    (-1, U64_MAX + 1, True, 0.0, "0", _IntegerSubclass(0)),
)
@pytest.mark.parametrize(
    "sequence_type", (PublicationSequence, LeaderboardSnapshotSequence)
)
def test_sequences_require_exact_nonnegative_u64(
    sequence_type: type[PublicationSequence | LeaderboardSnapshotSequence],
    invalid: object,
) -> None:
    with pytest.raises(LeaderboardRequestError):
        sequence_type(invalid)  # type: ignore[arg-type]
    assert sequence_type(0).value == 0
    assert sequence_type(U64_MAX).value == U64_MAX


@pytest.mark.parametrize(
    "invalid", (None, b"ascii", 1, _StringSubclass("ascii"), "non-ascii-é", "\ud800")
)
def test_cursor_requires_an_exact_ascii_string(invalid: object) -> None:
    with pytest.raises(LeaderboardRequestError):
        LeaderboardCursor(invalid)  # type: ignore[arg-type]
    assert LeaderboardCursor("").value == ""
    assert LeaderboardCursor("AZaz09-._~").value == "AZaz09-._~"


@pytest.mark.parametrize(
    "invalid", (0, -1, U64_MAX + 1, True, 1.0, "1", _IntegerSubclass(1))
)
def test_request_page_size_requires_exact_positive_u64(invalid: object) -> None:
    with pytest.raises(LeaderboardRequestError):
        ListFixtureLeaderboardRequest(  # type: ignore[arg-type]
            CHALLENGE_KEY, invalid, None
        )


@pytest.mark.parametrize(
    "invalid", (0, -1, U64_MAX + 1, True, 1.0, "1", _IntegerSubclass(1))
)
@pytest.mark.parametrize("field_name", MODEL_FIELDS[FixtureLeaderboardResourceLimits])
def test_each_resource_limit_requires_exact_positive_u64(
    field_name: str, invalid: object
) -> None:
    with pytest.raises(LeaderboardRequestError):
        _limits(**{field_name: invalid})


def test_resource_limits_are_required_and_copied_by_service() -> None:
    signature = inspect.signature(FixtureLeaderboardResourceLimits)
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    limits = _limits(max_page_size=2)
    provider = _Provider(_snapshot((_candidate(1), _candidate(2))))
    service = FixtureLeaderboardService(provider, limits)
    object.__setattr__(limits, "max_page_size", 1)
    page = service.list_entries(_request(page_size=2))
    assert len(page.rows) == 2
    invalid = _limits()
    object.__setattr__(invalid, "max_page_size", True)
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardService(provider, invalid)


def test_owner_nominals_are_exact_and_reconstructed() -> None:
    class ChallengeKeySubclass(ChallengeKey):
        pass

    class SubmissionIdSubclass(SubmissionId):
        pass

    with pytest.raises(LeaderboardRequestError):
        ListFixtureLeaderboardRequest(
            ChallengeKeySubclass("a10_fixture", "fixture-1.0"), 1, None
        )
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardCandidate(
            SubmissionIdSubclass("00000000-0000-4000-8000-000000000001"),
            "result-1",
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            ScoreStatus.SCORED,
            0.5,
            True,
            True,
            False,
            PublicationSequence(1),
        )

    request_key = ChallengeKey("a10_fixture", "fixture-1.0")
    request = ListFixtureLeaderboardRequest(request_key, 1, None)
    assert request.challenge_key == request_key
    assert request.challenge_key is not request_key
    candidate_id = _submission_id(9)
    candidate = _candidate(9, submission_id=candidate_id, challenge_key=request_key)
    assert candidate.submission_id == candidate_id
    assert candidate.submission_id is not candidate_id
    assert candidate.challenge_key == request_key
    assert candidate.challenge_key is not request_key


def test_public_owner_validators_are_applied_without_coercion() -> None:
    for result_id in ("", "bad value", "a" * 65, _StringSubclass("result-1")):
        with pytest.raises(LeaderboardRequestError):
            _candidate(result_id=result_id)  # type: ignore[arg-type]
    for digest in (
        "a" * 64,
        "sha256:" + "g" * 64,
        _StringSubclass(SCORING_PACK_HASH),
    ):
        with pytest.raises(LeaderboardRequestError):
            _candidate(scoring_pack_hash=digest)  # type: ignore[arg-type]


def _forged_score_status() -> ScoreStatus:
    status = str.__new__(ScoreStatus, ScoreStatus.SCORED.value)
    object.__setattr__(status, "_name_", "SCORED")
    object.__setattr__(status, "_value_", ScoreStatus.SCORED.value)
    return status


@pytest.mark.parametrize(
    "changes",
    (
        {"score_status": "SCORED"},
        {"score_status": _forged_score_status()},
        {"overall_score": 0},
        {"overall_score": True},
        {"overall_score": _FloatSubclass(0.5)},
        {"overall_score": math.nan},
        {"overall_score": math.inf},
        {"overall_score": -math.inf},
        {"mandatory_gates_passed": 1},
        {"fixture_origin": 1},
        {"eligible_for_emission": 0},
    ),
)
def test_candidate_constructor_requires_exact_provider_field_shapes(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "submission_id": _submission_id(1),
        "result_id": "result-1",
        "challenge_key": CHALLENGE_KEY,
        "scoring_pack_hash": SCORING_PACK_HASH,
        "score_status": ScoreStatus.SCORED,
        "overall_score": 0.5,
        "mandatory_gates_passed": True,
        "fixture_origin": True,
        "eligible_for_emission": False,
        "publication_sequence": PublicationSequence(1),
    }
    values.update(changes)
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardCandidate(**values)  # type: ignore[arg-type]

    for status in ScoreStatus:
        assert _candidate(score_status=status).score_status is status
    assert math.copysign(1.0, _candidate(overall_score=-0.0).overall_score) < 0.0
    assert _candidate(overall_score=-1.0).overall_score == -1.0
    assert _candidate(overall_score=2.0).overall_score == 2.0
    assert _candidate(mandatory_gates_passed=False).mandatory_gates_passed is False
    assert _candidate(fixture_origin=False).fixture_origin is False
    assert _candidate(eligible_for_emission=True).eligible_for_emission is True


def test_candidate_preserves_exact_score_and_pack_but_hides_private_ids() -> None:
    score = math.nextafter(0.5, 1.0)
    candidate = _candidate(7, overall_score=score)
    assert candidate.overall_score == score
    assert candidate.scoring_pack_hash == SCORING_PACK_HASH
    rendered = repr(candidate)
    assert candidate.submission_id.value not in rendered
    assert candidate.result_id not in rendered
    with pytest.raises(TypeError):
        pickle.dumps(candidate)


@pytest.mark.parametrize(
    "candidates",
    ([], {}, iter(()), _TupleSubclass(()), (object(),)),
)
def test_snapshot_requires_an_exact_tuple_of_exact_candidates(
    candidates: object,
) -> None:
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardCandidateSnapshot(
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            LeaderboardSnapshotSequence(1),
            candidates,  # type: ignore[arg-type]
        )
    assert _snapshot().candidates == ()


def test_nominal_subclasses_are_rejected() -> None:
    class PublicationSequenceSubclass(PublicationSequence):
        pass

    class SnapshotSequenceSubclass(LeaderboardSnapshotSequence):
        pass

    class CursorSubclass(LeaderboardCursor):
        pass

    class RequestSubclass(ListFixtureLeaderboardRequest):
        pass

    class CandidateSubclass(FixtureLeaderboardCandidate):
        pass

    class SnapshotSubclass(FixtureLeaderboardCandidateSnapshot):
        pass

    class LimitsSubclass(FixtureLeaderboardResourceLimits):
        pass

    class RowSubclass(FixtureLeaderboardRow):
        pass

    class PageSubclass(FixtureLeaderboardPage):
        pass

    row = FixtureLeaderboardRow(
        1,
        CHALLENGE_KEY,
        SCORING_PACK_HASH,
        0.5,
        True,
        PublicationSequence(1),
        True,
        False,
    )
    constructors = (
        lambda: PublicationSequenceSubclass(1),
        lambda: SnapshotSequenceSubclass(1),
        lambda: CursorSubclass("ascii"),
        lambda: RequestSubclass(CHALLENGE_KEY, 1, None),
        lambda: CandidateSubclass(
            _submission_id(1),
            "result-1",
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            ScoreStatus.SCORED,
            0.5,
            True,
            True,
            False,
            PublicationSequence(1),
        ),
        lambda: SnapshotSubclass(
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            LeaderboardSnapshotSequence(1),
            (),
        ),
        lambda: LimitsSubclass(1, 1, 1, 1, 1, 1),
        lambda: RowSubclass(
            1,
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            0.5,
            True,
            PublicationSequence(1),
            True,
            False,
        ),
        lambda: PageSubclass(
            "1.0",
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            LeaderboardSnapshotSequence(1),
            (row,),
            None,
            True,
            False,
        ),
    )
    for construct in constructors:
        with pytest.raises(LeaderboardRequestError):
            construct()


def test_public_row_and_page_exact_invariants() -> None:
    row = FixtureLeaderboardRow(
        1,
        CHALLENGE_KEY,
        SCORING_PACK_HASH,
        0.0,
        True,
        PublicationSequence(0),
        True,
        False,
    )
    page = FixtureLeaderboardPage(
        "1.0",
        CHALLENGE_KEY,
        SCORING_PACK_HASH,
        LeaderboardSnapshotSequence(0),
        (row,),
        None,
        True,
        False,
    )
    assert page.rows == (row,)
    assert page.rows[0] is not row
    invalid_rows = (
        _forge(
            FixtureLeaderboardRow,
            rank=0,
            challenge_key=CHALLENGE_KEY,
            scoring_pack_hash=SCORING_PACK_HASH,
            overall_score=0.0,
            mandatory_gates_passed=True,
            publication_sequence=PublicationSequence(0),
            fixture_origin=True,
            eligible_for_emission=False,
        ),
        _forge(FixtureLeaderboardRow, rank=1),
    )
    for invalid in invalid_rows:
        with pytest.raises(LeaderboardRequestError):
            FixtureLeaderboardPage(
                "1.0",
                CHALLENGE_KEY,
                SCORING_PACK_HASH,
                LeaderboardSnapshotSequence(0),
                (invalid,),
                None,
                True,
                False,
            )
    with pytest.raises(LeaderboardRequestError):
        FixtureLeaderboardPage(
            "2.0",
            CHALLENGE_KEY,
            SCORING_PACK_HASH,
            LeaderboardSnapshotSequence(0),
            (),
            None,
            True,
            False,
        )


def test_first_page_provider_arguments_call_count_and_owned_projection() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)))
    provider = _Provider(snapshot)
    request = _request(page_size=10)
    page = _service(provider).list_entries(request)
    assert len(provider.calls) == 1
    provider_key, sequence = provider.calls[0]
    assert provider_key == CHALLENGE_KEY and provider_key is not request.challenge_key
    assert sequence is None
    assert page.schema_version == "1.0"
    assert page.challenge_key == CHALLENGE_KEY
    assert page.challenge_key is not snapshot.challenge_key
    assert page.snapshot_sequence == snapshot.snapshot_sequence
    assert page.snapshot_sequence is not snapshot.snapshot_sequence
    assert type(page.rows) is tuple
    assert page.next_cursor is None
    assert page.fixture_origin is True
    assert page.eligible_for_emission is False


def test_exact_none_is_unavailable_but_empty_snapshot_is_success() -> None:
    unavailable = _Provider(None)
    with pytest.raises(LeaderboardUnavailableError) as raised:
        _service(unavailable).list_entries(_request())
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert len(unavailable.calls) == 1

    available = _Provider(_snapshot())
    page = _service(available).list_entries(_request())
    assert page.rows == ()
    assert page.next_cursor is None
    assert page.scoring_pack_hash == SCORING_PACK_HASH


@pytest.mark.parametrize("wrong", (False, 0, (), {}, object()))
def test_non_none_wrong_provider_returns_map_to_integration(wrong: object) -> None:
    provider = _Provider(None)
    provider.value = wrong  # type: ignore[assignment]
    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(provider).list_entries(_request())
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_missing_uncallable_and_subclassed_provider_results_fail_closed() -> None:
    class Missing:
        pass

    class Uncallable:
        get_snapshot = 1

    class WrongSignature:
        def get_snapshot(self) -> FixtureLeaderboardCandidateSnapshot:
            return _snapshot()

    class SnapshotSubclass(FixtureLeaderboardCandidateSnapshot):
        pass

    source = _snapshot()
    subclassed = _forge(
        SnapshotSubclass,
        challenge_key=source.challenge_key,
        scoring_pack_hash=source.scoring_pack_hash,
        snapshot_sequence=source.snapshot_sequence,
        candidates=source.candidates,
    )
    for provider in (
        Missing(),
        Uncallable(),
        WrongSignature(),
        _Provider(subclassed),
    ):
        with pytest.raises(LeaderboardIntegrationError) as raised:
            _service(provider).list_entries(_request())
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None


def test_provider_descriptor_failure_is_translated_only_at_call_time() -> None:
    class DescriptorProvider:
        reads = 0

        @property
        def get_snapshot(self) -> object:
            self.reads += 1
            raise RuntimeError("private descriptor canary")

    provider = DescriptorProvider()
    service = _service(provider)
    assert provider.reads == 0
    with pytest.raises(LeaderboardIntegrationError) as raised:
        service.list_entries(_request())
    assert provider.reads == 1
    assert "canary" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    "provider_error",
    (
        RuntimeError("private runtime canary"),
        LeaderboardRequestError(),
        LeaderboardResourceError(),
        LeaderboardUnavailableError(),
        LeaderboardIntegrationError(),
    ),
)
def test_every_provider_exception_becomes_a_new_integration_error(
    provider_error: Exception,
) -> None:
    provider = _Provider(_snapshot(), failure=provider_error)
    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(provider).list_entries(_request())
    assert raised.value is not provider_error
    assert type(raised.value) is LeaderboardIntegrationError
    assert "canary" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert provider_error not in raised.value.__dict__.values()


def test_provider_exception_repr_and_str_are_never_invoked() -> None:
    class HostileException(Exception):
        def __repr__(self) -> str:
            raise AssertionError("provider exception repr invoked")

        def __str__(self) -> str:
            raise AssertionError("provider exception str invoked")

    failure = HostileException(_Hostile())
    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(_Provider(_snapshot(), failure=failure)).list_entries(_request())
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    "process_control",
    (KeyboardInterrupt("stop"), SystemExit(7), GeneratorExit("close")),
)
def test_non_exception_baseexceptions_propagate_unchanged(
    process_control: BaseException,
) -> None:
    provider = _Provider(_snapshot(), failure=process_control)
    with pytest.raises(type(process_control)) as raised:
        _service(provider).list_entries(_request())
    assert raised.value is process_control


def test_capacity_is_nonblocking_precedes_internal_copy_and_releases() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(_Provider):
        def get_snapshot(
            self,
            challenge_key: ChallengeKey,
            snapshot_sequence: LeaderboardSnapshotSequence | None,
        ) -> FixtureLeaderboardCandidateSnapshot | None:
            self.calls.append((challenge_key, snapshot_sequence))
            entered.set()
            assert release.wait(timeout=5)
            return self.value

    provider = BlockingProvider(_snapshot((_candidate(),)))
    service = _service(provider, limits=_limits(max_concurrent_calls=1))
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            service.list_entries(_request())
        except BaseException as exc:  # noqa: BLE001 - asserted below
            failures.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(timeout=5)
    with pytest.raises(LeaderboardRequestError):
        service.list_entries(object())  # type: ignore[arg-type]
    forged_request = _forge(ListFixtureLeaderboardRequest)
    with pytest.raises(LeaderboardResourceError):
        service.list_entries(forged_request)
    assert len(provider.calls) == 1
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and not failures
    with pytest.raises(LeaderboardRequestError):
        service.list_entries(forged_request)
    assert len(provider.calls) == 1
    assert len(service.list_entries(_request()).rows) == 1


@pytest.mark.parametrize(
    "failure", (RuntimeError("ordinary"), KeyboardInterrupt("process-control"))
)
def test_capacity_is_restored_after_translated_and_propagated_failures(
    failure: BaseException,
) -> None:
    provider = _Provider(_snapshot(), failure=failure)
    service = _service(provider, limits=_limits(max_concurrent_calls=1))
    with pytest.raises(
        LeaderboardIntegrationError if isinstance(failure, Exception) else type(failure)
    ):
        service.list_entries(_request())
    provider.failure = None
    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == 2


def test_invalid_request_cursor_and_capacity_paths_do_not_call_provider() -> None:
    provider = _Provider(_snapshot())
    service = _service(provider, limits=_limits(max_page_size=1))
    for request in (
        object(),
        _forge(
            ListFixtureLeaderboardRequest,
            challenge_key=_Hostile(),
            page_size=1,
            cursor=None,
        ),
        _request(page_size=2),
        _request(cursor=LeaderboardCursor("not-a-canonical-cursor")),
    ):
        with pytest.raises((LeaderboardRequestError, LeaderboardResourceError)):
            service.list_entries(request)  # type: ignore[arg-type]
    assert provider.calls == []


@pytest.mark.parametrize(
    "changes",
    (
        {"score_status": ScoreStatus.MANDATORY_GATE_FAILED},
        {"score_status": ScoreStatus.PACK_NOT_READY},
        {"score_status": _forged_score_status()},
        {"overall_score": True},
        {"overall_score": 0},
        {"overall_score": _FloatSubclass(0.5)},
        {"overall_score": math.nan},
        {"overall_score": math.inf},
        {"overall_score": -0.0},
        {"overall_score": -0.01},
        {"overall_score": 1.01},
        {"mandatory_gates_passed": False},
        {"mandatory_gates_passed": 1},
        {"fixture_origin": False},
        {"fixture_origin": 1},
        {"eligible_for_emission": True},
        {"eligible_for_emission": 0},
        {"challenge_key": OTHER_CHALLENGE_KEY},
        {"scoring_pack_hash": OTHER_SCORING_PACK_HASH},
    ),
)
def test_forged_ineligible_provider_candidate_rejects_whole_snapshot(
    changes: dict[str, object],
) -> None:
    valid = _candidate(1)
    invalid = _forged_candidate(valid, **changes)
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(valid, invalid)))
    with pytest.raises(LeaderboardIntegrationError):
        _service(provider).list_entries(_request())
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "replacement",
    (
        _Hostile(),
        _StringSubclass("result-1"),
        _IntegerSubclass(1),
        _TupleSubclass(()),
    ),
)
def test_hostile_nested_values_fail_without_repr_equality_or_hashing(
    replacement: object,
) -> None:
    invalid = _forged_candidate(_candidate(), submission_id=replacement)
    with pytest.raises(LeaderboardIntegrationError):
        _service(
            _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
        ).list_entries(_request())


def test_snapshot_bound_is_committed_before_candidate_access() -> None:
    malformed = _forged_snapshot(_snapshot(), candidates=(_Hostile(), _Hostile()))
    service = _service(_Provider(malformed), limits=_limits(max_snapshot_rows=1))
    with pytest.raises(LeaderboardResourceError):
        service.list_entries(_request())


@pytest.mark.parametrize("duplicate_kind", ("submission", "result", "publication"))
def test_duplicate_provider_identity_rejects_the_complete_snapshot(
    duplicate_kind: str,
) -> None:
    first = _candidate(1, overall_score=0.9)
    changes: dict[str, object] = {}
    if duplicate_kind == "submission":
        changes["submission_id"] = first.submission_id
    elif duplicate_kind == "result":
        changes["result_id"] = first.result_id
    else:
        changes["publication_sequence"] = first.publication_sequence
    second = _candidate(2, overall_score=0.1, **changes)  # type: ignore[arg-type]
    with pytest.raises(LeaderboardIntegrationError):
        _service(_Provider(_snapshot((first, second)))).list_entries(_request())


@pytest.mark.parametrize(
    "snapshot",
    (
        _snapshot((_candidate(1, challenge_key=OTHER_CHALLENGE_KEY),)),
        _snapshot((_candidate(1, scoring_pack_hash=OTHER_SCORING_PACK_HASH),)),
        _snapshot((_candidate(1),), challenge_key=OTHER_CHALLENGE_KEY),
        _snapshot((_candidate(1),), scoring_pack_hash=OTHER_SCORING_PACK_HASH),
    ),
)
def test_mixed_challenge_or_pack_snapshots_fail_without_partial_page(
    snapshot: FixtureLeaderboardCandidateSnapshot,
) -> None:
    with pytest.raises(LeaderboardIntegrationError):
        _service(_Provider(snapshot)).list_entries(_request())


def test_complete_snapshot_is_sorted_and_competition_ranked_before_slice() -> None:
    candidates = (
        _candidate(4, overall_score=0.8, publication_sequence=PublicationSequence(9)),
        _candidate(2, overall_score=0.9, publication_sequence=PublicationSequence(5)),
        _candidate(3, overall_score=0.8, publication_sequence=PublicationSequence(1)),
        _candidate(1, overall_score=0.9, publication_sequence=PublicationSequence(2)),
    )
    provider = _Provider(_snapshot(candidates))
    service = _service(provider)

    first = service.list_entries(_request(page_size=2))
    assert tuple(row.overall_score for row in first.rows) == (0.9, 0.9)
    assert tuple(row.publication_sequence.value for row in first.rows) == (2, 5)
    assert tuple(row.rank for row in first.rows) == (1, 1)
    assert first.next_cursor is not None

    second = service.list_entries(_request(page_size=1, cursor=first.next_cursor))
    assert tuple(row.overall_score for row in second.rows) == (0.8,)
    assert tuple(row.publication_sequence.value for row in second.rows) == (1,)
    assert tuple(row.rank for row in second.rows) == (3,)
    assert second.next_cursor is not None

    third = service.list_entries(_request(page_size=8, cursor=second.next_cursor))
    assert tuple(row.publication_sequence.value for row in third.rows) == (9,)
    assert tuple(row.rank for row in third.rows) == (3,)
    assert third.next_cursor is None
    assert [sequence for _, sequence in provider.calls] == [
        None,
        LeaderboardSnapshotSequence(17),
        LeaderboardSnapshotSequence(17),
    ]


def test_exact_float_equality_is_the_only_tie_rule_and_scores_are_preserved() -> None:
    lower = 0.5
    higher = math.nextafter(lower, 1.0)
    candidates = (
        _candidate(1, overall_score=lower),
        _candidate(2, overall_score=higher),
        _candidate(3, overall_score=lower),
    )
    page = _service(_Provider(_snapshot(candidates))).list_entries(_request())
    assert tuple(row.overall_score for row in page.rows) == (higher, lower, lower)
    assert tuple(row.rank for row in page.rows) == (1, 2, 2)
    assert all(row.scoring_pack_hash == SCORING_PACK_HASH for row in page.rows)


def test_provider_order_cannot_change_final_order_or_rank() -> None:
    candidates = (
        _candidate(1, overall_score=0.25, publication_sequence=PublicationSequence(8)),
        _candidate(2, overall_score=0.75, publication_sequence=PublicationSequence(3)),
        _candidate(3, overall_score=0.75, publication_sequence=PublicationSequence(1)),
    )
    first_page = _service(_Provider(_snapshot(candidates))).list_entries(_request())
    reverse_snapshot = _snapshot(tuple(reversed(candidates)))
    reverse_page = _service(_Provider(reverse_snapshot)).list_entries(_request())
    assert first_page == reverse_page
    assert tuple(row.publication_sequence.value for row in first_page.rows) == (1, 3, 8)
    assert tuple(row.rank for row in first_page.rows) == (1, 1, 3)


def test_one_row_is_emitted_for_each_provider_approved_candidate() -> None:
    candidates = tuple(_candidate(index) for index in range(1, 6))
    page = _service(_Provider(_snapshot(candidates))).list_entries(_request())
    assert len(page.rows) == len(candidates)
    assert not hasattr(page, "total_count")
    assert not hasattr(page, "submission_count")


def _cursor_parts(cursor: LeaderboardCursor) -> tuple[str, ...]:
    return tuple(cursor.value.split("|"))


def _cursor_with_offset(cursor: LeaderboardCursor, offset: int) -> LeaderboardCursor:
    parts = list(_cursor_parts(cursor))
    value = str(offset)
    parts[-1] = f"next_offset={len(value)}:{value}"
    return LeaderboardCursor("|".join(parts))


def test_cursor_has_exact_schema_fields_board_literal_and_canonical_encoding() -> None:
    first, _, _ = _valid_page(page_size=1)
    assert first.next_cursor is not None
    cursor = first.next_cursor
    parts = _cursor_parts(cursor)
    assert tuple(part.partition("=")[0] for part in parts) == (
        "schema_version",
        "board_kind",
        "challenge_id",
        "challenge_version",
        "scoring_pack_hash",
        "snapshot_sequence",
        "next_offset",
    )
    assert parts[0] == "schema_version=3:1.0"
    assert parts[1] == "board_kind=19:fixture_leaderboard"
    assert cursor.value.isascii()
    assert "page_size" not in cursor.value

    again, _, _ = _valid_page(page_size=1)
    assert again.next_cursor == cursor
    assert repr(cursor) == "LeaderboardCursor(<opaque>)"


def test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset() -> None:
    candidates = tuple(_candidate(index) for index in range(1, 6))
    provider = _Provider(_snapshot(candidates, sequence=U64_MAX))
    service = _service(provider)
    first = service.list_entries(_request(page_size=2))
    assert first.next_cursor is not None
    second = service.list_entries(_request(page_size=2, cursor=first.next_cursor))
    assert second.next_cursor is not None
    third = service.list_entries(_request(page_size=1, cursor=second.next_cursor))
    assert third.next_cursor is None
    assert tuple(row.publication_sequence.value for row in first.rows) == (1, 2)
    assert tuple(row.publication_sequence.value for row in second.rows) == (3, 4)
    assert tuple(row.publication_sequence.value for row in third.rows) == (5,)
    assert provider.calls[0][1] is None
    for _, sequence in provider.calls[1:]:
        assert sequence == LeaderboardSnapshotSequence(U64_MAX)
        assert type(sequence) is LeaderboardSnapshotSequence


def test_terminal_offset_is_allowed_but_offset_beyond_snapshot_is_invalid() -> None:
    provider = _Provider(_snapshot((_candidate(1), _candidate(2))))
    service = _service(provider)
    first = service.list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    terminal_cursor = _cursor_with_offset(first.next_cursor, 2)
    terminal = service.list_entries(_request(cursor=terminal_cursor))
    assert terminal.rows == ()
    assert terminal.next_cursor is None
    calls_before = len(provider.calls)
    with pytest.raises(LeaderboardRequestError):
        service.list_entries(_request(cursor=_cursor_with_offset(first.next_cursor, 3)))
    assert len(provider.calls) == calls_before + 1


def test_malformed_unknown_reordered_and_noncanonical_cursors_are_rejected() -> None:
    page, provider, service = _valid_page(page_size=1)
    assert page.next_cursor is not None
    parts = list(_cursor_parts(page.next_cursor))
    reordered = parts.copy()
    reordered[0], reordered[1] = reordered[1], reordered[0]
    variants = (
        LeaderboardCursor(page.next_cursor.value + "|unknown=1:x"),
        LeaderboardCursor("|".join(reordered)),
        LeaderboardCursor(page.next_cursor.value[:-1]),
        LeaderboardCursor(" " + page.next_cursor.value),
        LeaderboardCursor(page.next_cursor.value.replace("3:1.0", "03:1.0", 1)),
        LeaderboardCursor(
            page.next_cursor.value.replace(
                "19:fixture_leaderboard", "19:official_leaderboard", 1
            )
        ),
        LeaderboardCursor(""),
    )
    initial_calls = len(provider.calls)
    for cursor in variants:
        with pytest.raises(LeaderboardRequestError):
            service.list_entries(_request(cursor=cursor))
    assert len(provider.calls) == initial_calls


def test_cursor_is_challenge_bound_before_provider_call() -> None:
    page, provider, service = _valid_page(page_size=1)
    assert page.next_cursor is not None
    initial_calls = len(provider.calls)
    with pytest.raises(LeaderboardRequestError):
        service.list_entries(
            _request(challenge_key=OTHER_CHALLENGE_KEY, cursor=page.next_cursor)
        )
    assert len(provider.calls) == initial_calls


@pytest.mark.parametrize("mismatch", ("challenge", "pack", "sequence"))
def test_continuation_cannot_drift_or_fall_forward(mismatch: str) -> None:
    provider = _Provider(_snapshot((_candidate(1), _candidate(2)), sequence=11))
    service = _service(provider)
    first = service.list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    if mismatch == "challenge":
        provider.value = _snapshot(
            (_candidate(1, challenge_key=OTHER_CHALLENGE_KEY),),
            challenge_key=OTHER_CHALLENGE_KEY,
            sequence=11,
        )
    elif mismatch == "pack":
        provider.value = _snapshot(
            (_candidate(1, scoring_pack_hash=OTHER_SCORING_PACK_HASH),),
            scoring_pack_hash=OTHER_SCORING_PACK_HASH,
            sequence=11,
        )
    else:
        provider.value = _snapshot((_candidate(1),), sequence=12)
    with pytest.raises(LeaderboardIntegrationError):
        service.list_entries(_request(cursor=first.next_cursor))
    assert provider.calls[-1][1] == LeaderboardSnapshotSequence(11)


def test_missing_first_or_stale_continuation_have_the_same_unavailable_error() -> None:
    with pytest.raises(LeaderboardUnavailableError) as first_missing:
        _service(_Provider(None)).list_entries(_request())

    provider = _Provider(_snapshot((_candidate(1), _candidate(2))))
    service = _service(provider)
    first = service.list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    provider.value = None
    with pytest.raises(LeaderboardUnavailableError) as stale:
        service.list_entries(_request(cursor=first.next_cursor))
    assert stale.value.code == first_missing.value.code
    assert stale.value.message == first_missing.value.message
    assert stale.value.__cause__ is None and stale.value.__context__ is None


def test_page_size_and_snapshot_row_bounds_are_exact() -> None:
    candidates = tuple(_candidate(index) for index in range(1, 4))
    provider = _Provider(_snapshot(candidates))
    service = _service(
        provider,
        limits=_limits(max_page_size=2, max_snapshot_rows=3),
    )
    assert len(service.list_entries(_request(page_size=2)).rows) == 2
    calls_before = len(provider.calls)
    with pytest.raises(LeaderboardResourceError):
        service.list_entries(_request(page_size=3))
    assert len(provider.calls) == calls_before

    over_provider = _Provider(_snapshot(candidates + (_candidate(4),)))
    with pytest.raises(LeaderboardResourceError):
        _service(over_provider, limits=_limits(max_snapshot_rows=3)).list_entries(
            _request()
        )
    assert len(over_provider.calls) == 1


@pytest.mark.parametrize(
    ("value", "width"),
    (
        ("ASCII", 5),
        ("é", 2),
        ("€", 3),
        ("😀", 4),
        ("Aé€😀", 10),
    ),
)
def test_utf8_capacity_counts_exact_valid_scalar_widths(
    value: str,
    width: int,
) -> None:
    require_utf8_capacity = sys.modules["carbon.leaderboard.service"].__dict__[
        "_require_utf8_capacity"
    ]

    require_utf8_capacity(value, width)
    with pytest.raises(LeaderboardResourceError) as raised:
        require_utf8_capacity(value, width - 1)
    assert type(raised.value) is LeaderboardResourceError


def test_utf8_capacity_stops_after_the_first_over_limit_scalar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = sys.modules["carbon.leaderboard.service"]
    require_utf8_capacity = service_module.__dict__["_require_utf8_capacity"]
    original_ord = ord
    visited: list[str] = []

    def counted_ord(character: str) -> int:
        visited.append(character)
        return original_ord(character)

    monkeypatch.setattr(service_module, "ord", counted_ord, raising=False)
    with pytest.raises(LeaderboardResourceError) as raised:
        require_utf8_capacity("ééAZ", 4)
    assert type(raised.value) is LeaderboardResourceError
    assert visited == ["é", "é", "A"]


def test_multibyte_submission_id_is_resource_safe_before_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "é" * 36
    assert len(oversized) <= string_limit
    assert len(oversized.encode("utf-8")) == string_limit + 1
    forged_submission = _forge(SubmissionId, value=oversized)
    invalid = _forged_candidate(
        _candidate(),
        submission_id=forged_submission,
    )
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    service = _service(
        provider,
        limits=_limits(
            max_string_utf8_bytes=string_limit,
            max_concurrent_calls=1,
        ),
    )
    original_post_init = SubmissionId.__post_init__
    oversized_owner_calls: list[str] = []

    def guarded_post_init(value: SubmissionId) -> None:
        raw = object.__getattribute__(value, "value")
        if raw == oversized:
            oversized_owner_calls.append(raw)
            raise AssertionError("byte-oversized SubmissionId reached owner validation")
        original_post_init(value)

    monkeypatch.setattr(SubmissionId, "__post_init__", guarded_post_init)
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert oversized_owner_calls == []
    assert len(provider.calls) == 1

    provider.value = _snapshot((_candidate(2),))
    assert len(service.list_entries(_request()).rows) == 1
    assert len(provider.calls) == 2


@pytest.mark.parametrize("oversized", ("é" * 36, "😀" * 18))
def test_multibyte_result_id_is_resource_safe_before_owner_validation(
    oversized: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    assert len(oversized) <= string_limit
    assert len(oversized.encode("utf-8")) == string_limit + 1
    invalid = _forged_candidate(_candidate(), result_id=oversized)
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    owner_calls: list[object] = []

    def sentinel(value: object) -> str:
        owner_calls.append(value)
        raise AssertionError("byte-oversized result_id reached owner validation")

    monkeypatch.setattr(
        sys.modules["carbon.leaderboard.service"],
        "validate_version",
        sentinel,
    )
    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert owner_calls == []
    assert len(provider.calls) == 1


@pytest.mark.parametrize("boundary", ("snapshot", "candidate"))
def test_multibyte_provider_hash_is_resource_safe_before_digest_validation(
    boundary: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "é" * 36
    assert len(oversized) <= string_limit
    assert len(oversized.encode("utf-8")) == string_limit + 1
    if boundary == "snapshot":
        snapshot = _forged_snapshot(
            _snapshot(),
            scoring_pack_hash=oversized,
        )
    else:
        invalid = _forged_candidate(
            _candidate(),
            scoring_pack_hash=oversized,
        )
        snapshot = _forged_snapshot(_snapshot(), candidates=(invalid,))
    provider = _Provider(snapshot)
    original_validator = sys.modules["carbon.leaderboard.service"].__dict__[
        "is_sha256_digest"
    ]
    oversized_validator_calls: list[str] = []

    def guarded_validator(value: object) -> bool:
        if value == oversized:
            oversized_validator_calls.append(oversized)
            raise AssertionError("byte-oversized hash reached digest validation")
        return original_validator(value)

    monkeypatch.setattr(
        sys.modules["carbon.leaderboard.service"],
        "is_sha256_digest",
        guarded_validator,
    )
    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert oversized_validator_calls == []
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("boundary", "expected_calls"),
    (("request", 0), ("provider", 1)),
)
def test_multibyte_challenge_identity_is_bounded_before_owner_validation(
    boundary: str,
    expected_calls: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "é" * 36
    assert len(oversized) <= string_limit
    assert len(oversized.encode("utf-8")) == string_limit + 1
    forged_key = _forge(
        ChallengeKey,
        challenge_id=oversized,
        version=CHALLENGE_KEY.version,
    )
    request = _request()
    if boundary == "request":
        request = _forge(
            ListFixtureLeaderboardRequest,
            challenge_key=forged_key,
            page_size=1,
            cursor=None,
        )
        provider = _Provider(_snapshot())
    else:
        provider = _Provider(_forged_snapshot(_snapshot(), challenge_key=forged_key))
    service = _service(
        provider,
        limits=_limits(
            max_string_utf8_bytes=string_limit,
            max_concurrent_calls=1,
        ),
    )
    original_post_init = ChallengeKey.__post_init__
    oversized_owner_calls: list[str] = []

    def guarded_post_init(value: ChallengeKey) -> None:
        challenge_id = object.__getattribute__(value, "challenge_id")
        if challenge_id == oversized:
            oversized_owner_calls.append(challenge_id)
            raise AssertionError("byte-oversized Challenge reached owner validation")
        original_post_init(value)

    monkeypatch.setattr(ChallengeKey, "__post_init__", guarded_post_init)
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(request)
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert oversized_owner_calls == []
    assert len(provider.calls) == expected_calls

    provider.value = _snapshot()
    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == expected_calls + 1


@pytest.mark.parametrize(
    ("cursor_limit", "string_limit"),
    ((71, 72), (72, 71), (71, 71)),
)
def test_multibyte_incoming_cursor_obeys_each_utf8_byte_limit(
    cursor_limit: int,
    string_limit: int,
) -> None:
    raw = "😀" * 18
    assert len(raw) <= min(cursor_limit, string_limit)
    assert len(raw.encode("utf-8")) == 72
    forged_cursor = _forge(LeaderboardCursor, value=raw)
    forged_request = _forge(
        ListFixtureLeaderboardRequest,
        challenge_key=CHALLENGE_KEY,
        page_size=1,
        cursor=forged_cursor,
    )
    provider = _Provider(_snapshot())
    service = _service(
        provider,
        limits=_limits(
            max_cursor_utf8_bytes=cursor_limit,
            max_string_utf8_bytes=string_limit,
            max_concurrent_calls=1,
        ),
    )

    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(forged_request)
    _assert_fixed_identifier_error(
        raised.value,
        raw,
        LeaderboardResourceError,
    )
    assert provider.calls == []

    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == 1


def test_multibyte_incoming_cursor_exact_byte_boundary_reaches_ascii_rule() -> None:
    raw = "😀" * 18
    width = len(raw.encode("utf-8"))
    forged_cursor = _forge(LeaderboardCursor, value=raw)
    forged_request = _forge(
        ListFixtureLeaderboardRequest,
        challenge_key=CHALLENGE_KEY,
        page_size=1,
        cursor=forged_cursor,
    )
    provider = _Provider(_snapshot())
    service = _service(
        provider,
        limits=_limits(
            max_cursor_utf8_bytes=width,
            max_string_utf8_bytes=width,
            max_concurrent_calls=1,
        ),
    )

    with pytest.raises(LeaderboardRequestError) as raised:
        service.list_entries(forged_request)
    _assert_fixed_identifier_error(
        raised.value,
        raw,
        LeaderboardRequestError,
    )
    assert provider.calls == []

    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    ("boundary", "expected_error", "expected_calls"),
    (
        ("request", LeaderboardRequestError, 0),
        ("provider", LeaderboardIntegrationError, 1),
    ),
)
def test_nonencodable_string_is_safe_and_releases_concurrency_capacity(
    boundary: str,
    expected_error: type[LeaderboardError],
    expected_calls: int,
) -> None:
    malformed = "\ud800" + "a" * 70
    forged_key = _forge(
        ChallengeKey,
        challenge_id=malformed,
        version=CHALLENGE_KEY.version,
    )
    request = _request()
    if boundary == "request":
        request = _forge(
            ListFixtureLeaderboardRequest,
            challenge_key=forged_key,
            page_size=1,
            cursor=None,
        )
        provider = _Provider(_snapshot())
    else:
        provider = _Provider(_forged_snapshot(_snapshot(), challenge_key=forged_key))
    service = _service(
        provider,
        limits=_limits(
            max_string_utf8_bytes=len(SCORING_PACK_HASH),
            max_concurrent_calls=1,
        ),
    )

    with pytest.raises(expected_error) as raised:
        service.list_entries(request)
    _assert_fixed_identifier_error(
        raised.value,
        malformed,
        expected_error,
    )
    assert len(provider.calls) == expected_calls

    provider.value = _snapshot()
    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == expected_calls + 1


def test_oversized_submission_id_is_resource_safe_and_releases_capacity() -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "s" * (string_limit + 1)
    forged_submission = _forge(SubmissionId, value=oversized)
    invalid = _forged_candidate(
        _candidate(),
        submission_id=forged_submission,
    )
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    service = _service(
        provider,
        limits=_limits(
            max_string_utf8_bytes=string_limit,
            max_concurrent_calls=1,
        ),
    )

    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert len(provider.calls) == 1

    provider.value = _snapshot((_candidate(2),))
    page = service.list_entries(_request())
    assert len(page.rows) == 1
    assert page.next_cursor is None
    assert len(provider.calls) == 2


def test_submission_capacity_precedes_owner_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "s" * (string_limit + 1)
    forged_submission = _forge(SubmissionId, value=oversized)
    invalid = _forged_candidate(
        _candidate(),
        submission_id=forged_submission,
    )
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    service = _service(
        provider,
        limits=_limits(max_string_utf8_bytes=string_limit),
    )
    owner_calls: list[str] = []

    def sentinel(value: SubmissionId) -> None:
        owner_calls.append(object.__getattribute__(value, "value"))
        raise AssertionError("oversized SubmissionId reached owner validation")

    monkeypatch.setattr(SubmissionId, "__post_init__", sentinel)
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(_request())
    assert type(raised.value) is LeaderboardResourceError
    assert owner_calls == []
    assert len(provider.calls) == 1


@pytest.mark.parametrize("malformed", ("0" * 36, "é" * 35))
def test_bounded_malformed_submission_id_is_integration_error(
    malformed: str,
) -> None:
    forged_submission = _forge(SubmissionId, value=malformed)
    invalid = _forged_candidate(
        _candidate(),
        submission_id=forged_submission,
    )
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))

    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=len(SCORING_PACK_HASH)),
        ).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        malformed,
        LeaderboardIntegrationError,
    )
    assert len(provider.calls) == 1


def test_submission_id_capacity_boundary_is_exact_and_freshly_owned() -> None:
    source = _submission_id(1)
    copy_submission_id = sys.modules["carbon.leaderboard.service"].__dict__[
        "_copy_submission_id"
    ]

    owned = copy_submission_id(
        source,
        _limits(max_string_utf8_bytes=36),
    )
    assert type(owned) is SubmissionId
    assert owned == source
    assert owned is not source
    with pytest.raises(LeaderboardResourceError) as raised:
        copy_submission_id(
            source,
            _limits(max_string_utf8_bytes=35),
        )
    assert type(raised.value) is LeaderboardResourceError


@pytest.mark.parametrize(
    "oversized",
    (
        "r" * (len(SCORING_PACK_HASH) + 1),
        "é" * (len(SCORING_PACK_HASH) + 1),
    ),
)
def test_oversized_result_id_is_resource_safe(oversized: str) -> None:
    string_limit = len(SCORING_PACK_HASH)
    invalid = _forged_candidate(_candidate(), result_id=oversized)
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))

    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert len(provider.calls) == 1


def test_result_capacity_precedes_owner_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "r" * (string_limit + 1)
    invalid = _forged_candidate(_candidate(), result_id=oversized)
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    service = _service(
        provider,
        limits=_limits(max_string_utf8_bytes=string_limit),
    )
    owner_calls: list[object] = []

    def sentinel(value: object) -> str:
        owner_calls.append(value)
        raise AssertionError("oversized result_id reached owner validation")

    monkeypatch.setattr(
        sys.modules["carbon.leaderboard.service"],
        "validate_version",
        sentinel,
    )
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(_request())
    assert type(raised.value) is LeaderboardResourceError
    assert owner_calls == []
    assert len(provider.calls) == 1


@pytest.mark.parametrize("malformed", ("bad value", "bad/value", "résult-1"))
def test_bounded_malformed_result_id_is_integration_error(
    malformed: str,
) -> None:
    invalid = _forged_candidate(_candidate(), result_id=malformed)
    provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))

    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(provider).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        malformed,
        LeaderboardIntegrationError,
    )
    assert len(provider.calls) == 1


def test_result_id_capacity_boundary_preserves_the_exact_string() -> None:
    source = "result-1"
    copy_result_id = sys.modules["carbon.leaderboard.service"].__dict__[
        "_copy_result_id"
    ]

    owned = copy_result_id(
        source,
        _limits(max_string_utf8_bytes=len(source)),
    )
    assert type(owned) is str
    assert owned is source
    with pytest.raises(LeaderboardResourceError) as raised:
        copy_result_id(
            source,
            _limits(max_string_utf8_bytes=len(source) - 1),
        )
    assert type(raised.value) is LeaderboardResourceError


@pytest.mark.parametrize("boundary", ("snapshot", "candidate"))
def test_oversized_provider_hash_has_resource_precedence(boundary: str) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "sha256:" + "a" * 65
    if boundary == "snapshot":
        snapshot = _forged_snapshot(
            _snapshot(),
            scoring_pack_hash=oversized,
        )
    else:
        invalid = _forged_candidate(
            _candidate(),
            scoring_pack_hash=oversized,
        )
        snapshot = _forged_snapshot(
            _snapshot(),
            candidates=(invalid,),
        )
    provider = _Provider(snapshot)

    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        oversized,
        LeaderboardResourceError,
    )
    assert len(provider.calls) == 1


def test_provider_hash_capacity_precedes_owner_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized = "sha256:" + "a" * 65
    provider = _Provider(
        _forged_snapshot(
            _snapshot(),
            scoring_pack_hash=oversized,
        )
    )
    service = _service(
        provider,
        limits=_limits(max_string_utf8_bytes=string_limit),
    )
    owner_calls: list[object] = []

    def sentinel(value: object) -> bool:
        owner_calls.append(value)
        raise AssertionError("oversized hash reached owner validation")

    monkeypatch.setattr(
        sys.modules["carbon.leaderboard.service"],
        "is_sha256_digest",
        sentinel,
    )
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(_request())
    assert type(raised.value) is LeaderboardResourceError
    assert owner_calls == []
    assert len(provider.calls) == 1


@pytest.mark.parametrize("boundary", ("snapshot", "candidate"))
def test_bounded_malformed_provider_hash_is_integration_error(boundary: str) -> None:
    malformed = "sha256:" + "g" * 64
    if boundary == "snapshot":
        snapshot = _forged_snapshot(
            _snapshot(),
            scoring_pack_hash=malformed,
        )
    else:
        invalid = _forged_candidate(
            _candidate(),
            scoring_pack_hash=malformed,
        )
        snapshot = _forged_snapshot(
            _snapshot(),
            candidates=(invalid,),
        )
    provider = _Provider(snapshot)

    with pytest.raises(LeaderboardIntegrationError) as raised:
        _service(provider).list_entries(_request())
    _assert_fixed_identifier_error(
        raised.value,
        malformed,
        LeaderboardIntegrationError,
    )
    assert len(provider.calls) == 1


def test_provider_hash_capacity_boundary_preserves_the_exact_string() -> None:
    copy_provider_hash = sys.modules["carbon.leaderboard.service"].__dict__[
        "_copy_provider_hash"
    ]

    owned = copy_provider_hash(
        SCORING_PACK_HASH,
        _limits(max_string_utf8_bytes=71),
    )
    assert type(owned) is str
    assert owned is SCORING_PACK_HASH
    with pytest.raises(LeaderboardResourceError) as raised:
        copy_provider_hash(
            SCORING_PACK_HASH,
            _limits(max_string_utf8_bytes=70),
        )
    assert type(raised.value) is LeaderboardResourceError


def test_provider_identifier_helpers_lock_capacity_before_owner_validation() -> None:
    source_path = LEADERBOARD_ROOT / "service.py"
    tree = ast.parse(
        source_path.read_text(encoding="utf-8"),
        filename=str(source_path),
    )
    functions = {
        node.name: node
        for node in tree.body
        if type(node) is ast.FunctionDef
        and node.name
        in {
            "_copy_submission_id",
            "_copy_result_id",
            "_copy_provider_hash",
        }
    }
    expected = {
        "_copy_submission_id": ("SubmissionId", True),
        "_copy_result_id": ("validate_version", True),
        "_copy_provider_hash": ("is_sha256_digest", False),
    }
    assert set(functions) == set(expected)
    for function_name, (owner_name, requires_ascii) in expected.items():
        calls = tuple(
            node
            for node in ast.walk(functions[function_name])
            if type(node) is ast.Call
        )
        capacity_calls = tuple(
            node
            for node in calls
            if type(node.func) is ast.Name
            and node.func.id == "_require_string_capacity"
        )
        owner_calls = tuple(
            node
            for node in calls
            if type(node.func) is ast.Name and node.func.id == owner_name
        )
        ascii_calls = tuple(
            node
            for node in calls
            if type(node.func) is ast.Attribute and node.func.attr == "isascii"
        )
        assert len(capacity_calls) == 1
        assert len(owner_calls) == 1
        assert capacity_calls[0].lineno < owner_calls[0].lineno
        if requires_ascii:
            assert len(ascii_calls) == 1
            assert capacity_calls[0].lineno < ascii_calls[0].lineno
            assert ascii_calls[0].lineno < owner_calls[0].lineno
        else:
            assert ascii_calls == ()


def test_utf8_capacity_source_policy_and_ascii_len_guards() -> None:
    source_path = LEADERBOARD_ROOT / "service.py"
    tree = ast.parse(
        source_path.read_text(encoding="utf-8"),
        filename=str(source_path),
    )
    functions = {node.name: node for node in tree.body if type(node) is ast.FunctionDef}

    primitive = functions["_require_utf8_capacity"]
    primitive_calls = tuple(
        node for node in ast.walk(primitive) if type(node) is ast.Call
    )
    assert not any(
        type(call.func) is ast.Attribute and call.func.attr == "encode"
        for call in primitive_calls
    )
    assert not {
        call.func.id for call in primitive_calls if type(call.func) is ast.Name
    }.intersection({"bytes", "bytearray", "memoryview", "repr", "str"})
    loops = tuple(node for node in ast.walk(primitive) if type(node) is ast.For)
    assert len(loops) == 1
    loop_resource_raises = tuple(
        node
        for node in ast.walk(loops[0])
        if type(node) is ast.Raise
        and type(node.exc) is ast.Call
        and type(node.exc.func) is ast.Name
        and node.exc.func.id == "LeaderboardResourceError"
    )
    assert len(loop_resource_raises) == 1

    wrapper = functions["_require_string_capacity"]
    wrapper_calls = tuple(node for node in ast.walk(wrapper) if type(node) is ast.Call)
    assert not any(
        type(call.func) is ast.Name and call.func.id == "len" for call in wrapper_calls
    )
    delegations = tuple(
        call
        for call in wrapper_calls
        if type(call.func) is ast.Name and call.func.id == "_require_utf8_capacity"
    )
    assert len(delegations) == 1
    assert type(delegations[0].args[0]) is ast.Name
    assert delegations[0].args[0].id == "value"
    assert _attribute_path(delegations[0].args[1]) == ("limits.max_string_utf8_bytes")

    wrapper_callers = {
        function.name
        for function in functions.values()
        if any(
            type(call.func) is ast.Name and call.func.id == "_require_string_capacity"
            for call in ast.walk(function)
            if type(call) is ast.Call
        )
    }
    assert wrapper_callers == {
        "_copy_provider_challenge",
        "_copy_provider_hash",
        "_copy_request_challenge",
        "_copy_request_hash",
        "_copy_result_id",
        "_copy_score_status",
        "_copy_submission_id",
    }

    cursor = functions["_copy_request_cursor"]
    cursor_calls = tuple(node for node in ast.walk(cursor) if type(node) is ast.Call)
    assert not any(
        type(call.func) is ast.Name and call.func.id == "len" for call in cursor_calls
    )
    cursor_capacity_calls = tuple(
        call
        for call in cursor_calls
        if type(call.func) is ast.Name and call.func.id == "_require_utf8_capacity"
    )
    assert len(cursor_capacity_calls) == 2
    assert tuple(
        (
            call.args[0].id if type(call.args[0]) is ast.Name else None,
            _attribute_path(call.args[1]),
        )
        for call in cursor_capacity_calls
    ) == (
        ("raw", "limits.max_cursor_utf8_bytes"),
        ("raw", "limits.max_string_utf8_bytes"),
    )
    cursor_ascii_calls = tuple(
        call
        for call in cursor_calls
        if type(call.func) is ast.Attribute and call.func.attr == "isascii"
    )
    assert len(cursor_ascii_calls) == 1
    assert cursor_capacity_calls[-1].lineno < cursor_ascii_calls[0].lineno

    for function_name, value_name in (
        ("_new_cursor", "raw"),
        ("_charge_response_text", "value"),
        ("_response_utf8_bytes", "cursor_value"),
    ):
        function = functions[function_name]
        calls = tuple(node for node in ast.walk(function) if type(node) is ast.Call)
        ascii_calls = tuple(
            call
            for call in calls
            if type(call.func) is ast.Attribute
            and call.func.attr == "isascii"
            and type(call.func.value) is ast.Name
            and call.func.value.id == value_name
        )
        len_calls = tuple(
            call
            for call in calls
            if type(call.func) is ast.Name
            and call.func.id == "len"
            and len(call.args) == 1
            and type(call.args[0]) is ast.Name
            and call.args[0].id == value_name
        )
        assert len(ascii_calls) == 1
        assert len_calls
        assert ascii_calls[0].lineno < min(call.lineno for call in len_calls)


def test_oversized_request_challenge_id_is_bounded_before_provider_call() -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized_id = "a" * (string_limit + 1)
    forged_key = _forge(
        ChallengeKey,
        challenge_id=oversized_id,
        version=CHALLENGE_KEY.version,
    )
    forged_request = _forge(
        ListFixtureLeaderboardRequest,
        challenge_key=forged_key,
        page_size=1,
        cursor=None,
    )
    provider = _Provider(_snapshot())
    service = _service(
        provider,
        limits=_limits(
            max_string_utf8_bytes=string_limit,
            max_concurrent_calls=1,
        ),
    )

    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(forged_request)
    assert type(raised.value) is LeaderboardResourceError
    assert provider.calls == []
    assert oversized_id not in str(raised.value)
    assert oversized_id not in repr(raised.value)
    assert oversized_id not in raised.value.args
    assert oversized_id not in raised.value.__dict__.values()

    assert service.list_entries(_request()).rows == ()
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "oversized_version",
    (
        "v" * (len(SCORING_PACK_HASH) + 1),
        "é" * (len(SCORING_PACK_HASH) + 1),
    ),
)
def test_oversized_request_challenge_version_has_resource_precedence(
    oversized_version: str,
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    forged_key = _forge(
        ChallengeKey,
        challenge_id=CHALLENGE_KEY.challenge_id,
        version=oversized_version,
    )
    forged_request = _forge(
        ListFixtureLeaderboardRequest,
        challenge_key=forged_key,
        page_size=1,
        cursor=None,
    )
    provider = _Provider(_snapshot())

    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(forged_request)
    assert type(raised.value) is LeaderboardResourceError
    assert provider.calls == []


def test_oversized_snapshot_challenge_precedes_candidate_access() -> None:
    string_limit = len(SCORING_PACK_HASH)
    forged_key = _forge(
        ChallengeKey,
        challenge_id="a" * (string_limit + 1),
        version=CHALLENGE_KEY.version,
    )
    unreadable_candidate = _forge(FixtureLeaderboardCandidate)
    snapshot = _forged_snapshot(
        _snapshot(),
        challenge_key=forged_key,
        candidates=(unreadable_candidate,),
    )
    provider = _Provider(snapshot)

    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    assert type(raised.value) is LeaderboardResourceError
    assert len(provider.calls) == 1


def test_oversized_candidate_challenge_rejects_the_whole_snapshot() -> None:
    string_limit = len(SCORING_PACK_HASH)
    forged_key = _forge(
        ChallengeKey,
        challenge_id="a" * (string_limit + 1),
        version=CHALLENGE_KEY.version,
    )
    invalid = _forged_candidate(_candidate(2), challenge_key=forged_key)
    snapshot = _forged_snapshot(
        _snapshot(),
        candidates=(_candidate(1), invalid),
    )
    provider = _Provider(snapshot)

    with pytest.raises(LeaderboardResourceError) as raised:
        _service(
            provider,
            limits=_limits(max_string_utf8_bytes=string_limit),
        ).list_entries(_request())
    assert type(raised.value) is LeaderboardResourceError
    assert len(provider.calls) == 1


@pytest.mark.parametrize("boundary", ("request", "snapshot", "candidate"))
def test_oversized_challenge_never_reaches_owner_reconstruction(
    boundary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    string_limit = len(SCORING_PACK_HASH)
    oversized_id = "a" * (string_limit + 1)
    forged_key = _forge(
        ChallengeKey,
        challenge_id=oversized_id,
        version=CHALLENGE_KEY.version,
    )
    request = _request()
    if boundary == "request":
        request = _forge(
            ListFixtureLeaderboardRequest,
            challenge_key=forged_key,
            page_size=1,
            cursor=None,
        )
        provider = _Provider(_snapshot())
    elif boundary == "snapshot":
        provider = _Provider(
            _forged_snapshot(
                _snapshot(),
                challenge_key=forged_key,
                candidates=(_forge(FixtureLeaderboardCandidate),),
            )
        )
    else:
        invalid = _forged_candidate(_candidate(), challenge_key=forged_key)
        provider = _Provider(_forged_snapshot(_snapshot(), candidates=(invalid,)))
    service = _service(
        provider,
        limits=_limits(max_string_utf8_bytes=string_limit),
    )
    original_post_init = ChallengeKey.__post_init__
    oversized_owner_calls: list[tuple[str, str]] = []

    def guarded_post_init(value: ChallengeKey) -> None:
        challenge_id = object.__getattribute__(value, "challenge_id")
        version = object.__getattribute__(value, "version")
        if challenge_id == oversized_id:
            oversized_owner_calls.append((challenge_id, version))
            raise AssertionError("oversized Challenge reached owner validation")
        original_post_init(value)

    monkeypatch.setattr(ChallengeKey, "__post_init__", guarded_post_init)
    with pytest.raises(LeaderboardResourceError) as raised:
        service.list_entries(request)
    assert type(raised.value) is LeaderboardResourceError
    assert oversized_owner_calls == []
    assert len(provider.calls) == (0 if boundary == "request" else 1)


@pytest.mark.parametrize(
    ("challenge_id", "version"),
    (
        ("bad value", CHALLENGE_KEY.version),
        ("aé", CHALLENGE_KEY.version),
        (CHALLENGE_KEY.challenge_id, "bad version"),
        (CHALLENGE_KEY.challenge_id, "fixture-é"),
    ),
)
@pytest.mark.parametrize(
    ("boundary", "expected_error", "expected_calls"),
    (
        ("request", LeaderboardRequestError, 0),
        ("provider", LeaderboardIntegrationError, 1),
    ),
)
def test_bounded_malformed_challenge_keeps_boundary_error_mapping(
    challenge_id: str,
    version: str,
    boundary: str,
    expected_error: type[LeaderboardError],
    expected_calls: int,
) -> None:
    forged_key = _forge(
        ChallengeKey,
        challenge_id=challenge_id,
        version=version,
    )
    request = _request()
    if boundary == "request":
        request = _forge(
            ListFixtureLeaderboardRequest,
            challenge_key=forged_key,
            page_size=1,
            cursor=None,
        )
        provider = _Provider(_snapshot())
    else:
        provider = _Provider(_forged_snapshot(_snapshot(), challenge_key=forged_key))

    with pytest.raises(expected_error) as raised:
        _service(provider).list_entries(request)
    assert type(raised.value) is expected_error
    assert len(provider.calls) == expected_calls


def test_string_limit_is_per_occurrence_and_exact_at_boundary() -> None:
    provider = _Provider(_snapshot((_candidate(),)))
    exact = _service(
        provider,
        limits=_limits(max_string_utf8_bytes=len(SCORING_PACK_HASH.encode("utf-8"))),
    ).list_entries(_request())
    assert len(exact.rows) == 1
    with pytest.raises(LeaderboardResourceError):
        _service(
            _Provider(_snapshot((_candidate(),))),
            limits=_limits(
                max_string_utf8_bytes=len(SCORING_PACK_HASH.encode("utf-8")) - 1
            ),
        ).list_entries(_request())


def test_emitted_cursor_obeys_both_cursor_and_string_byte_limits() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)))
    baseline = _service(_Provider(snapshot)).list_entries(_request(page_size=1))
    assert baseline.next_cursor is not None
    cursor_bytes = len(baseline.next_cursor.value.encode("utf-8"))

    for field_name in ("max_cursor_utf8_bytes", "max_string_utf8_bytes"):
        exact_limits = _limits(**{field_name: cursor_bytes})
        exact = _service(_Provider(snapshot), limits=exact_limits).list_entries(
            _request(page_size=1)
        )
        assert exact.next_cursor == baseline.next_cursor
        with pytest.raises(LeaderboardResourceError):
            _service(
                _Provider(snapshot),
                limits=_limits(**{field_name: cursor_bytes - 1}),
            ).list_entries(_request(page_size=1))


def test_incoming_cursor_obeys_both_bounds_before_provider_invocation() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)))
    first = _service(_Provider(snapshot)).list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    cursor_bytes = len(first.next_cursor.value.encode("utf-8"))
    for field_name in ("max_cursor_utf8_bytes", "max_string_utf8_bytes"):
        provider = _Provider(snapshot)
        service = _service(
            provider,
            limits=_limits(**{field_name: cursor_bytes - 1}),
        )
        with pytest.raises(LeaderboardResourceError):
            service.list_entries(_request(cursor=first.next_cursor))
        assert provider.calls == []


def test_exact_response_formula_repeated_occurrences_and_one_byte_over() -> None:
    candidates = (
        _candidate(1, overall_score=0.9),
        _candidate(2, overall_score=0.8),
        _candidate(3, overall_score=0.7),
    )
    snapshot = _snapshot(candidates)
    baseline = _service(_Provider(snapshot)).list_entries(_request(page_size=2))
    assert baseline.next_cursor is not None
    measured = _response_utf8_bytes(baseline)
    expected_without_cursor = (
        len(b"1.0")
        + len(CHALLENGE_KEY.challenge_id.encode("utf-8"))
        + len(CHALLENGE_KEY.version.encode("utf-8"))
        + len(SCORING_PACK_HASH.encode("utf-8"))
        + 2
        * (
            len(CHALLENGE_KEY.challenge_id.encode("utf-8"))
            + len(CHALLENGE_KEY.version.encode("utf-8"))
            + len(SCORING_PACK_HASH.encode("utf-8"))
        )
    )
    assert measured == expected_without_cursor + len(
        baseline.next_cursor.value.encode("utf-8")
    )

    exact = _service(
        _Provider(snapshot), limits=_limits(max_response_utf8_bytes=measured)
    ).list_entries(_request(page_size=2))
    assert exact == baseline
    with pytest.raises(LeaderboardResourceError):
        _service(
            _Provider(snapshot),
            limits=_limits(max_response_utf8_bytes=measured - 1),
        ).list_entries(_request(page_size=2))


def test_identity_shared_strings_are_still_charged_per_occurrence() -> None:
    shared_hash = "".join(("sha256:", "c" * 64))
    candidate = _candidate(1, scoring_pack_hash=shared_hash)
    snapshot = _snapshot((candidate,), scoring_pack_hash=shared_hash)
    baseline = _service(_Provider(snapshot)).list_entries(_request())
    assert baseline.scoring_pack_hash is baseline.rows[0].scoring_pack_hash
    measured = _response_utf8_bytes(baseline)
    exact = _service(
        _Provider(snapshot), limits=_limits(max_response_utf8_bytes=measured)
    ).list_entries(_request())
    assert exact == baseline
    with pytest.raises(LeaderboardResourceError):
        _service(
            _Provider(snapshot),
            limits=_limits(max_response_utf8_bytes=measured - 1),
        ).list_entries(_request())


def test_empty_page_response_charge_is_exact() -> None:
    snapshot = _snapshot()
    baseline = _service(_Provider(snapshot)).list_entries(_request())
    measured = _response_utf8_bytes(baseline)
    assert measured == sum(
        len(value.encode("utf-8"))
        for value in (
            "1.0",
            CHALLENGE_KEY.challenge_id,
            CHALLENGE_KEY.version,
            SCORING_PACK_HASH,
        )
    )
    assert (
        _service(
            _Provider(snapshot), limits=_limits(max_response_utf8_bytes=measured)
        ).list_entries(_request())
        == baseline
    )
    with pytest.raises(LeaderboardResourceError):
        _service(
            _Provider(snapshot),
            limits=_limits(max_response_utf8_bytes=measured - 1),
        ).list_entries(_request())


def test_incoming_cursor_is_excluded_from_response_meter() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)))
    first = _service(_Provider(snapshot)).list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    terminal_cursor = _cursor_with_offset(first.next_cursor, 2)
    baseline = _service(_Provider(snapshot)).list_entries(
        _request(cursor=terminal_cursor)
    )
    assert baseline.rows == () and baseline.next_cursor is None
    measured = _response_utf8_bytes(baseline)
    assert len(terminal_cursor.value.encode("utf-8")) > measured
    exact = _service(
        _Provider(snapshot), limits=_limits(max_response_utf8_bytes=measured)
    ).list_entries(_request(cursor=terminal_cursor))
    assert exact == baseline


def test_emitted_cursor_is_charged_once_without_decoded_payload_duplication() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)))
    page = _service(_Provider(snapshot)).list_entries(_request(page_size=1))
    assert page.next_cursor is not None
    measured = _response_utf8_bytes(page)
    exact = _service(
        _Provider(snapshot), limits=_limits(max_response_utf8_bytes=measured)
    ).list_entries(_request(page_size=1))
    assert exact == page


def test_fixed_errors_are_not_recursively_response_metered() -> None:
    limits = _limits(max_response_utf8_bytes=1)
    with pytest.raises(LeaderboardUnavailableError):
        _service(_Provider(None), limits=limits).list_entries(_request())
    provider = _Provider(_snapshot())
    with pytest.raises(LeaderboardRequestError):
        _service(provider, limits=limits).list_entries(  # type: ignore[arg-type]
            object()
        )
    assert provider.calls == []


def test_provider_snapshot_mutation_after_return_cannot_change_page() -> None:
    source_candidate = _candidate(1, overall_score=0.625)
    source_snapshot = _snapshot((source_candidate,))
    provider = _Provider(source_snapshot)
    page = _service(provider).list_entries(_request())
    expected = page

    object.__setattr__(source_candidate, "overall_score", 0.0)
    object.__setattr__(source_candidate, "challenge_key", OTHER_CHALLENGE_KEY)
    object.__setattr__(source_snapshot, "scoring_pack_hash", OTHER_SCORING_PACK_HASH)
    object.__setattr__(source_snapshot, "candidates", ())
    assert page == expected
    assert page.rows[0].overall_score == 0.625
    assert page.challenge_key == CHALLENGE_KEY
    assert page.scoring_pack_hash == SCORING_PACK_HASH


def test_provider_mutation_during_callback_cannot_change_owned_request() -> None:
    class MutatingProvider:
        def get_snapshot(
            self,
            challenge_key: ChallengeKey,
            snapshot_sequence: LeaderboardSnapshotSequence | None,
        ) -> FixtureLeaderboardCandidateSnapshot:
            del snapshot_sequence
            object.__setattr__(challenge_key, "challenge_id", "mutated")
            return _snapshot((_candidate(),))

    page = _service(MutatingProvider()).list_entries(_request())
    assert page.challenge_key == CHALLENGE_KEY
    assert page.rows[0].challenge_key == CHALLENGE_KEY


def test_continuation_provider_cannot_mutate_retained_cursor_sequence() -> None:
    snapshot = _snapshot((_candidate(1), _candidate(2)), sequence=17)

    class MutatingContinuationProvider:
        def get_snapshot(
            self,
            challenge_key: ChallengeKey,
            snapshot_sequence: LeaderboardSnapshotSequence | None,
        ) -> FixtureLeaderboardCandidateSnapshot:
            assert challenge_key == CHALLENGE_KEY
            if snapshot_sequence is not None:
                object.__setattr__(snapshot_sequence, "value", 999)
            return snapshot

    service = _service(MutatingContinuationProvider())
    first = service.list_entries(_request(page_size=1))
    assert first.next_cursor is not None
    continuation = service.list_entries(_request(page_size=1, cursor=first.next_cursor))
    assert continuation.snapshot_sequence == LeaderboardSnapshotSequence(17)
    assert tuple(row.publication_sequence.value for row in continuation.rows) == (2,)
    assert continuation.next_cursor is None


def test_reentrant_provider_callback_is_bounded_without_deadlock() -> None:
    class ReentrantProvider:
        service: FixtureLeaderboardService

        def __init__(self) -> None:
            self.inner_error: Exception | None = None
            self.calls = 0

        def get_snapshot(
            self,
            challenge_key: ChallengeKey,
            snapshot_sequence: LeaderboardSnapshotSequence | None,
        ) -> FixtureLeaderboardCandidateSnapshot:
            del challenge_key, snapshot_sequence
            self.calls += 1
            try:
                self.service.list_entries(_request())
            except Exception as exc:  # noqa: BLE001 - asserted exact below
                self.inner_error = exc
            return _snapshot()

    provider = ReentrantProvider()
    provider.service = _service(provider, limits=_limits(max_concurrent_calls=1))
    assert provider.service.list_entries(_request()).rows == ()
    assert type(provider.inner_error) is LeaderboardResourceError
    assert provider.calls == 1


def test_missing_and_container_substituted_provider_fields_fail_closed() -> None:
    source = _snapshot((_candidate(),))
    malformed_values = (
        _forge(
            FixtureLeaderboardCandidateSnapshot,
            challenge_key=source.challenge_key,
        ),
        _forged_snapshot(source, candidates=list(source.candidates)),
        _forged_snapshot(source, candidates=_TupleSubclass(source.candidates)),
        _forged_snapshot(source, candidates={0: source.candidates[0]}),
        _forged_snapshot(source, candidates=iter(source.candidates)),
    )
    for malformed in malformed_values:
        with pytest.raises(LeaderboardIntegrationError):
            _service(_Provider(malformed)).list_entries(_request())


def test_no_provider_owned_private_alias_is_reachable_from_success() -> None:
    candidate = _candidate(23, result_id="private-result-23")
    snapshot = _snapshot((candidate,))
    provider = _Provider(snapshot)
    page = _service(provider).list_entries(_request())
    reached = _reachable_values(page)
    assert provider not in reached
    assert snapshot not in reached
    assert candidate not in reached
    assert not any(type(value) is SubmissionId for value in reached)
    assert candidate.submission_id.value not in reached
    assert candidate.result_id not in reached
    assert not any(
        type(value) is FixtureLeaderboardCandidateSnapshot for value in reached
    )
    assert not any(type(value) is FixtureLeaderboardCandidate for value in reached)


def test_public_allowlist_has_no_identity_time_diagnostics_or_economics() -> None:
    page, _, _ = _valid_page(page_size=1)
    assert (
        tuple(field.name for field in dataclasses.fields(page))
        == MODEL_FIELDS[FixtureLeaderboardPage]
    )
    assert tuple(field.name for field in dataclasses.fields(page.rows[0])) == (
        MODEL_FIELDS[FixtureLeaderboardRow]
    )
    assert page.fixture_origin is True
    assert page.eligible_for_emission is False
    assert page.rows[0].fixture_origin is True
    assert page.rows[0].eligible_for_emission is False
    public_names = {
        field.name
        for value in (page, page.rows[0])
        for field in dataclasses.fields(value)
    }
    for token in (
        "submission_id",
        "result_id",
        "requester",
        "hotkey",
        "wallet",
        "participant",
        "timestamp",
        "components",
        "diagnostics",
        "margin",
        "stress",
        "fee",
        "payment",
        "sponsor",
        "customer_value",
        "total_count",
        "rank_delta",
        "win_rate",
        "provider_metadata",
    ):
        assert token not in public_names


def test_cursor_and_public_representations_contain_no_hidden_material() -> None:
    candidate = _candidate(31, result_id="private-result-31")
    page = _service(_Provider(_snapshot((candidate, _candidate(32))))).list_entries(
        _request(page_size=1)
    )
    assert page.next_cursor is not None
    cursor_text = page.next_cursor.value.lower()
    for private in (
        candidate.submission_id.value,
        candidate.result_id,
        "requester",
        "hotkey",
        "wallet",
        "participant",
        "seed",
        "draw",
        "role",
        "domain",
        "context",
        "entropy",
        "timestamp",
        "expiry",
        "path",
        "provider",
        "fee",
        "payment",
        "margin",
        "stress",
        "diagnostic",
    ):
        assert private.lower() not in cursor_text
    rendered = repr(page)
    assert candidate.submission_id.value not in rendered
    assert candidate.result_id not in rendered


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


def test_response_meter_has_exact_explicit_field_manifest_and_order() -> None:
    source_path = LEADERBOARD_ROOT / "service.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    meter = next(
        node
        for node in tree.body
        if type(node) is ast.FunctionDef and node.name == "_response_utf8_bytes"
    )
    charged: list[str] = []
    assignments: dict[str, str] = {}
    for node in ast.walk(meter):
        if (
            type(node) is ast.Assign
            and len(node.targets) == 1
            and type(node.targets[0]) is ast.Name
        ):
            path = _attribute_path(node.value)
            if path is not None:
                assignments[node.targets[0].id] = path
    for node in ast.walk(meter):
        if type(node) is not ast.Call or type(node.func) is not ast.Name:
            continue
        if node.func.id != "_charge_response_text" or len(node.args) < 2:
            continue
        path = _attribute_path(node.args[1])
        if type(node.args[1]) is ast.Name:
            path = assignments.get(node.args[1].id, path)
        assert path is not None
        charged.append(path)
    assert tuple(charged) == (
        "page.schema_version",
        "page.challenge_key.challenge_id",
        "page.challenge_key.version",
        "page.scoring_pack_hash",
        "row.challenge_key.challenge_id",
        "row.challenge_key.version",
        "row.scoring_pack_hash",
        "page.next_cursor.value",
    )
    assert not any(
        name in ".".join(charged)
        for name in (
            "rank",
            "overall_score",
            "mandatory_gates_passed",
            "publication_sequence",
            "snapshot_sequence",
            "fixture_origin",
            "eligible_for_emission",
            "rows",
            "field_name",
        )
    )


def test_meter_uses_no_reflection_serialization_or_wire_representation() -> None:
    service_source = (LEADERBOARD_ROOT / "service.py").read_text(encoding="utf-8")
    tree = ast.parse(service_source)
    meter = next(
        node
        for node in tree.body
        if type(node) is ast.FunctionDef and node.name == "_response_utf8_bytes"
    )
    prohibited_calls = {
        node.func.id
        for node in ast.walk(meter)
        if type(node) is ast.Call
        and type(node.func) is ast.Name
        and node.func.id
        in {
            "asdict",
            "fields",
            "getattr",
            "repr",
            "str",
            "vars",
        }
    }
    assert prohibited_calls == set()
    assert not any(
        type(node) is ast.Attribute
        and node.attr in {"dumps", "encode_json", "to_dict", "__dict__"}
        for node in ast.walk(meter)
    )


def test_dependency_import_and_runtime_escape_policy() -> None:
    files = tuple(sorted(LEADERBOARD_ROOT.glob("*.py")))
    assert tuple(path.name for path in files) == (
        "__init__.py",
        "model.py",
        "providers.py",
        "service.py",
    )
    owner_allowlist = {
        "carbon.registry": {
            "ChallengeKey",
            "is_sha256_digest",
            "validate_version",
        },
        "carbon.scoring": {"ScoreStatus"},
        "carbon.fees": {"SubmissionId"},
    }
    allowed_relative_modules = {None, "model", "providers", "service"}
    forbidden_runtime_names = {
        "__import__",
        "asdict",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "import_module",
        "locals",
        "vars",
    }
    forbidden_modules = {
        "aiohttp",
        "copy",
        "datetime",
        "flask",
        "http",
        "importlib",
        "json",
        "marshal",
        "os",
        "pathlib",
        "pickle",
        "requests",
        "shelve",
        "socket",
        "tempfile",
        "time",
        "urllib",
    }
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
                    assert node.module in allowed_relative_modules
                elif node.module in owner_allowlist:
                    assert {alias.name for alias in node.names} <= owner_allowlist[
                        node.module
                    ]
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
                    "import_module",
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
                if type(node.func) is ast.Name and node.func.id in {
                    "isinstance",
                    "issubclass",
                }:
                    assert not any(
                        type(argument) is ast.Name
                        and argument.id == "FixtureLeaderboardProvider"
                        for argument in node.args[1:]
                    )
                if type(node.func) is ast.Name:
                    assert node.func.id != "repr"
        assert not any(
            type(node) is ast.Name and node.id == "runtime_checkable"
            for node in ast.walk(tree)
        )


def test_source_has_no_private_owner_or_deferred_authority_dependency() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(LEADERBOARD_ROOT.glob("*.py"))
    )
    for prohibited in (
        "InternalResult",
        "ScoreEngine",
        "EvaluationCard",
        "CardStore",
        "SubmissionService",
        "RequesterIdentity",
        "SubmissionStatusView",
        "TrainEval",
        "McpService",
        "PublishedPrior",
        "PublishedScaffold",
        "StructuralEstimate",
        "Landscape",
        "FrontierRecord",
        "FrontierAdvanceEvent",
        "ProductQualification",
        "bittensor",
        "numpy",
        "scipy",
        "torch",
        "pydantic",
        "fastapi",
    ):
        assert prohibited not in source


def test_service_owns_no_cache_store_history_or_background_state() -> None:
    provider = _Provider(_snapshot())
    service = _service(provider)
    assert not hasattr(service, "__dict__")
    assert tuple(type(service).__slots__) == (
        "_active_calls",
        "_admission_lock",
        "_limits",
        "_provider",
    )
    assert not any(
        token in slot
        for slot in type(service).__slots__
        for token in (
            "cache",
            "database",
            "history",
            "refresh",
            "scheduler",
            "store",
            "timestamp",
        )
    )


def test_import_with_optional_and_later_dependencies_blocked(tmp_path: Path) -> None:
    script = f"""
import importlib
import importlib.abc
import sys

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})

blocked_roots = {{
    'aiohttp', 'bittensor', 'docker', 'econml', 'fastapi', 'flask', 'h5py',
    'jax', 'neuralop', 'numpy', 'pandas', 'physicsnemo', 'pydantic', 'requests',
    'scipy', 'sklearn', 'torch', 'tqdm', 'yaml',
}}
blocked_carbon = (
    'carbon.audit', 'carbon.chain', 'carbon.emission',
    'carbon.evaluation', 'carbon.landscape', 'carbon.logging_utils',
    'carbon.mcp', 'carbon.qualification', 'carbon.traineval',
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
module = importlib.import_module('carbon.leaderboard')
assert module.__all__ == {PUBLIC_EXPORTS!r}
export_names = tuple(getattr(module, name).__name__ for name in module.__all__)
assert export_names == module.__all__
assert attempted == []
print(module.__file__)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_fresh_no_dependency_wheel_imports_exact_surface_outside_tree(
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
    environment = tmp_path / "venv"
    create = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert create.returncode == 0, create.stderr
    python = environment / "bin" / "python"
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
    outside = tmp_path / "outside"
    outside.mkdir()
    script = f"""
import importlib
import importlib.abc
import importlib.metadata
import pathlib
import sys

blocked_roots = {{
    'aiohttp', 'bittensor', 'docker', 'econml', 'fastapi', 'flask', 'h5py',
    'jax', 'neuralop', 'numpy', 'pandas', 'physicsnemo', 'pydantic', 'requests',
    'scipy', 'sklearn', 'torch', 'tqdm', 'yaml',
}}
blocked_carbon = (
    'carbon.audit', 'carbon.chain', 'carbon.emission', 'carbon.evaluation',
    'carbon.landscape', 'carbon.logging_utils', 'carbon.mcp',
    'carbon.qualification', 'carbon.traineval',
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
leaderboard = importlib.import_module('carbon.leaderboard')
from carbon.fees import SubmissionId
from carbon.registry import ChallengeKey
from carbon.scoring import ScoreStatus

assert importlib.metadata.version('carbon') == '0.9.0'
requirements = importlib.metadata.requires('carbon') or ()
assert all('extra ==' in requirement.lower() for requirement in requirements)
assert leaderboard.__all__ == {PUBLIC_EXPORTS!r}
export_names = tuple(
    getattr(leaderboard, name).__name__ for name in leaderboard.__all__
)
assert export_names == leaderboard.__all__
assert {str(source)!r} not in str(pathlib.Path(leaderboard.__file__).resolve())
assert attempted == []
assert not any(
    name.partition('.')[0] in blocked_roots
    or any(name == prefix or name.startswith(prefix + '.') for prefix in blocked_carbon)
    for name in sys.modules
)
key = ChallengeKey('a10_fixture', 'fixture-1.0')
candidate = leaderboard.FixtureLeaderboardCandidate(
    SubmissionId('00000000-0000-4000-8000-000000000001'),
    'result-1', key, {SCORING_PACK_HASH!r}, ScoreStatus.SCORED, 0.5,
    True, True, False, leaderboard.PublicationSequence(1),
)
snapshot = leaderboard.FixtureLeaderboardCandidateSnapshot(
    key, {SCORING_PACK_HASH!r}, leaderboard.LeaderboardSnapshotSequence(1),
    (candidate,),
)
class Provider:
    def get_snapshot(self, challenge_key, snapshot_sequence):
        assert challenge_key == key
        assert snapshot_sequence is None
        return snapshot
limits = leaderboard.FixtureLeaderboardResourceLimits(8, 8, 4096, 4096, 4096, 1)
page = leaderboard.FixtureLeaderboardService(Provider(), limits).list_entries(
    leaderboard.ListFixtureLeaderboardRequest(key, 8, None)
)
assert len(page.rows) == 1 and page.rows[0].rank == 1
print(pathlib.Path(leaderboard.__file__).resolve())
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
