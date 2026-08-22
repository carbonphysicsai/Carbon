"""CPU acceptance tests for A6's bounded card-store disclosure boundary."""

from __future__ import annotations

import builtins
import copy
import dataclasses
import gc
import json
import math
import os
import pickle
import shutil
import subprocess
import sys
import textwrap
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from carbon import cards
from carbon.cards import (
    CardAuthorizationError,
    CardConflictError,
    CardNotFoundError,
    CardProjectionError,
    CardRecordKey,
    CardRequestError,
    CardStore,
    CardStoreError,
    CardWriteDisposition,
    EvaluationCard,
    EvaluationComponentScores,
    EvaluationGateResult,
    RequesterAuthorizationKey,
)
from carbon.cards import store as store_module
from carbon.registry import ChallengeKey
from carbon.scoring.model import (
    GateDecision,
    InternalResult,
    LegScore,
    ScalarScore,
    ScorePackPin,
    ScoreStatus,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCORING_DIGEST = "sha256:" + "a" * 64
GENERATOR_DIGEST = "sha256:" + "b" * 64
ALTERNATE_SCORING_DIGEST = "sha256:" + "c" * 64
ALTERNATE_GENERATOR_DIGEST = "sha256:" + "d" * 64
LEG_ORDER = ("physics", "robustness", "accuracy")
PUBLIC_EXPORTS = (
    "CardAuthorizationError",
    "CardConflictError",
    "CardNotFoundError",
    "CardProjectionError",
    "CardRecordKey",
    "CardRequestError",
    "CardStore",
    "CardStoreError",
    "CardWriteDisposition",
    "EvaluationCard",
    "EvaluationComponentScores",
    "EvaluationGateResult",
    "RequesterAuthorizationKey",
)
CARD_FIELDS = (
    "schema_version",
    "result_id",
    "status",
    "scoring_pack_hash",
    "overall_score",
    "component_scores",
    "gate_results",
    "failure_tags",
    "fixture_origin",
    "eligible_for_emission",
    "public_diagnostics",
    "disclosure_tier",
)


class _StringSubclass(str):
    pass


class _FloatSubclass(float):
    pass


class _TupleSubclass(tuple[object, ...]):
    pass


class _ComponentScoresSubclass(EvaluationComponentScores):
    __slots__ = ()


class _GateResultSubclass(EvaluationGateResult):
    __slots__ = ()


class _HostileString(str):
    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile string equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile string hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile string repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile string str was invoked")


class _HostileTuple(tuple[object, ...]):
    def __iter__(self) -> object:
        raise AssertionError("hostile tuple iteration was invoked")

    def __len__(self) -> int:
        raise AssertionError("hostile tuple length was invoked")

    def __getitem__(self, index: object) -> object:
        del index
        raise AssertionError("hostile tuple indexing was invoked")

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile tuple equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile tuple hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile tuple repr was invoked")


class _HostileRecordKey(CardRecordKey):
    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile record-key equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile record-key hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile record-key repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile record-key str was invoked")


class _HostileRequesterKey(RequesterAuthorizationKey):
    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile requester-key equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile requester-key hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile requester-key repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile requester-key str was invoked")


class _HostileInternalResult(InternalResult):
    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile result equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile result hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile result repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile result str was invoked")


class _HostileScorePackPin(ScorePackPin):
    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile pin equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile pin hashing was invoked")

    def __repr__(self) -> str:
        raise AssertionError("hostile pin repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile pin str was invoked")


def _pin(
    *,
    challenge_key: ChallengeKey | None = None,
    scoring_version: str = "fixture-1.0",
    scoring_digest: str = SCORING_DIGEST,
    generator_version_required: str = "fixture-1.0",
    generator_digest_required: str = GENERATOR_DIGEST,
) -> ScorePackPin:
    return ScorePackPin(
        challenge_key=challenge_key or ChallengeKey("a6_fixture", "fixture-1.0"),
        scoring_version=scoring_version,
        scoring_digest=scoring_digest,
        generator_version_required=generator_version_required,
        generator_digest_required=generator_digest_required,
        schema_version="1.0",
        numerical_profile="python_binary64_v1",
        fixture_origin=True,
    )


def _gate_decisions(*, optional_passed: bool = False) -> tuple[GateDecision, ...]:
    return (
        GateDecision("mandatory_gate", True, True),
        GateDecision("optional_diagnostic", optional_passed, False),
    )


def _leg_scores(
    *,
    physics: float = 0.25,
    robustness: float = 0.5,
    accuracy: float = 0.75,
    component_prefix: str = "private_component",
) -> tuple[LegScore, ...]:
    top_level = (physics, robustness, accuracy)
    fine_grained = (0.125, 0.375, 0.625)
    return tuple(
        LegScore(
            leg,
            (ScalarScore(f"{component_prefix}_{leg}", fine_score),),
            leg_score,
        )
        for leg, leg_score, fine_score in zip(
            LEG_ORDER, top_level, fine_grained, strict=True
        )
    )


def _result(
    status: ScoreStatus = ScoreStatus.SCORED,
    *,
    pin: ScorePackPin | None = None,
) -> InternalResult:
    selected_pin = pin or _pin()
    if status is ScoreStatus.SCORED:
        return InternalResult(
            status=status,
            pack_pin=selected_pin,
            gate_decisions=_gate_decisions(),
            leg_scores=_leg_scores(),
            combined_score=0.625,
            eligible_for_emission=False,
        )
    if status is ScoreStatus.MANDATORY_GATE_FAILED:
        return InternalResult(
            status=status,
            pack_pin=selected_pin,
            gate_decisions=(
                GateDecision("mandatory_gate", False, True),
                GateDecision("optional_diagnostic", True, False),
            ),
            leg_scores=(),
            combined_score=0.0,
            eligible_for_emission=False,
        )
    if status is ScoreStatus.PACK_NOT_READY:
        return InternalResult(
            status=status,
            pack_pin=selected_pin,
            gate_decisions=(),
            leg_scores=(),
            combined_score=None,
            eligible_for_emission=False,
        )
    raise AssertionError("test factory received an unsupported status")


def _unsafe_copy_exact(value: object, **overrides: object) -> object:
    copied = object.__new__(type(value))
    for field in fields(value):
        field_value = overrides.get(field.name, getattr(value, field.name))
        object.__setattr__(copied, field.name, field_value)
    return copied


def _single_private_record(store: CardStore) -> object:
    records = store._records  # type: ignore[attr-defined]
    assert len(records) == 1
    return next(iter(records.values()))


def _assert_fixed_error(
    error: BaseException,
    *,
    error_type: type[BaseException],
    code: str,
    message: str,
    canaries: tuple[str, ...] = (),
) -> None:
    assert type(error) is error_type
    assert error.code == code  # type: ignore[attr-defined]
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = f"{type(error).__name__}: {error!r} {error!s}"
    assert all(canary not in rendered for canary in canaries)


def _card_kwargs(status: str = "SCORED") -> dict[str, object]:
    common: dict[str, object] = {
        "schema_version": "1.0",
        "result_id": "result-1.0",
        "status": status,
        "scoring_pack_hash": SCORING_DIGEST,
        "fixture_origin": True,
        "eligible_for_emission": False,
        "public_diagnostics": (),
        "disclosure_tier": "phase0_budgeted",
    }
    if status == "SCORED":
        common.update(
            {
                "overall_score": 0.625,
                "component_scores": EvaluationComponentScores(0.25, 0.5, 0.75),
                "gate_results": (
                    EvaluationGateResult("mandatory_gate", True),
                    EvaluationGateResult("optional_diagnostic", False),
                ),
                "failure_tags": (),
            }
        )
    elif status == "MANDATORY_GATE_FAILED":
        common.update(
            {
                "overall_score": 0.0,
                "component_scores": None,
                "gate_results": (
                    EvaluationGateResult("mandatory_gate", False),
                    EvaluationGateResult("optional_diagnostic", True),
                ),
                "failure_tags": ("mandatory_gate_failed",),
            }
        )
    elif status == "PACK_NOT_READY":
        common.update(
            {
                "overall_score": None,
                "component_scores": None,
                "gate_results": (),
                "failure_tags": (),
            }
        )
    else:
        raise AssertionError("test factory received an unsupported public status")
    return common


@pytest.mark.parametrize("key_type", (CardRecordKey, RequesterAuthorizationKey))
@pytest.mark.parametrize(
    "token",
    ("a", "A", "v1", "Alpha-2.3_test", "x" * 64),
)
def test_nominal_keys_accept_exact_bounded_tokens(
    key_type: type[CardRecordKey | RequesterAuthorizationKey], token: str
) -> None:
    key = key_type(token)

    assert key.value == token
    assert type(key.value) is str


@pytest.mark.parametrize("key_type", (CardRecordKey, RequesterAuthorizationKey))
@pytest.mark.parametrize(
    "token",
    (
        "",
        " leading",
        "trailing ",
        "contains space",
        "unicode-é",
        ".leading",
        "trailing-",
        "double..separator",
        "slash/value",
        "x" * 65,
    ),
)
def test_nominal_keys_reject_malformed_tokens_without_echo(
    key_type: type[CardRecordKey | RequesterAuthorizationKey], token: str
) -> None:
    with pytest.raises(CardRequestError) as captured:
        key_type(token)

    _assert_fixed_error(
        captured.value,
        error_type=CardRequestError,
        code="card.request.invalid",
        message="Card request is invalid.",
        canaries=(token,) if token else (),
    )


@pytest.mark.parametrize("key_type", (CardRecordKey, RequesterAuthorizationKey))
@pytest.mark.parametrize(
    "value",
    (None, True, 1, b"token", _StringSubclass("token")),
)
def test_nominal_keys_require_exact_builtin_strings(
    key_type: type[CardRecordKey | RequesterAuthorizationKey], value: object
) -> None:
    with pytest.raises(CardRequestError) as captured:
        key_type(value)  # type: ignore[arg-type]

    _assert_fixed_error(
        captured.value,
        error_type=CardRequestError,
        code="card.request.invalid",
        message="Card request is invalid.",
    )


@pytest.mark.parametrize("key_type", (CardRecordKey, RequesterAuthorizationKey))
def test_nominal_keys_do_not_normalize_trim_or_casefold(
    key_type: type[CardRecordKey | RequesterAuthorizationKey],
) -> None:
    upper = key_type("Opaque-Token")
    lower = key_type("opaque-token")

    assert upper.value == "Opaque-Token"
    assert lower.value == "opaque-token"
    assert upper != lower
    with pytest.raises(CardRequestError):
        key_type(" Opaque-Token ")
    with pytest.raises(CardRequestError):
        key_type("Opaque-Å")


@pytest.mark.parametrize("key_type", (CardRecordKey, RequesterAuthorizationKey))
def test_nominal_key_representations_are_opaque(
    key_type: type[CardRecordKey | RequesterAuthorizationKey],
) -> None:
    canary = "Opaque-Representation-Canary"
    key = key_type(canary)

    assert canary not in repr(key)
    assert canary not in str(key)


@pytest.mark.parametrize(
    "operation",
    ("write-record", "write-requester", "read-record", "read-requester"),
)
def test_nominal_key_wrappers_are_not_cross_interchangeable(operation: str) -> None:
    store = CardStore()
    record_key: object = CardRecordKey("record")
    requester_key: object = RequesterAuthorizationKey("requester")
    if operation.endswith("record"):
        record_key = RequesterAuthorizationKey("record")
    else:
        requester_key = CardRecordKey("requester")

    with pytest.raises(CardRequestError):
        if operation.startswith("write"):
            store.write_internal(
                record_key,  # type: ignore[arg-type]
                requester_key,  # type: ignore[arg-type]
                _result(),
            )
        else:
            store.read_budgeted(
                record_key,  # type: ignore[arg-type]
                requester_key,  # type: ignore[arg-type]
            )


@pytest.mark.parametrize(
    ("error_type", "base", "code", "message"),
    (
        (
            CardRequestError,
            ValueError,
            "card.request.invalid",
            "Card request is invalid.",
        ),
        (
            CardNotFoundError,
            LookupError,
            "card.record.not_found",
            "Card record was not found.",
        ),
        (
            CardAuthorizationError,
            PermissionError,
            "card.authorization.denied",
            "Card access is not authorized.",
        ),
        (
            CardConflictError,
            RuntimeError,
            "card.record.conflict",
            "Card record conflicts with existing data.",
        ),
        (
            CardStoreError,
            RuntimeError,
            "card.store.failure",
            "Card store operation failed.",
        ),
        (
            CardProjectionError,
            RuntimeError,
            "card.projection.failure",
            "Card projection failed.",
        ),
    ),
)
def test_error_contracts_are_fixed_non_echoing_and_not_caller_controlled(
    error_type: type[BaseException],
    base: type[BaseException],
    code: str,
    message: str,
) -> None:
    assert error_type.__bases__ == (base,)
    error = error_type()
    _assert_fixed_error(
        error,
        error_type=error_type,
        code=code,
        message=message,
    )

    with pytest.raises(TypeError):
        error_type("caller-controlled-canary")
    with pytest.raises(TypeError):
        error_type(code="caller-controlled-code")


def test_component_scores_preserve_a5_binary64_values_including_negative_zero() -> None:
    scores = EvaluationComponentScores(-0.0, math.nextafter(0.5, 1.0), 1.0)

    assert math.copysign(1.0, scores.physics) == -1.0
    assert scores.robustness == math.nextafter(0.5, 1.0)
    assert scores.accuracy == 1.0


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("physics", 0),
        ("physics", True),
        ("physics", _FloatSubclass(0.5)),
        ("physics", -0.01),
        ("robustness", 1.01),
        ("robustness", float("nan")),
        ("accuracy", float("inf")),
        ("accuracy", -float("inf")),
    ),
)
def test_component_scores_reject_non_exact_or_out_of_range_values(
    field_name: str, value: object
) -> None:
    values: dict[str, object] = {
        "physics": 0.25,
        "robustness": 0.5,
        "accuracy": 0.75,
    }
    values[field_name] = value

    with pytest.raises((TypeError, ValueError)):
        EvaluationComponentScores(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("gate_id", "passed"),
    (
        ("Not_Canonical", True),
        ("contains space", True),
        ("unicode_é", True),
        (_StringSubclass("valid_gate"), True),
        ("valid_gate", 1),
        ("valid_gate", _StringSubclass("true")),
    ),
)
def test_public_gate_results_require_exact_canonical_values(
    gate_id: object, passed: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvaluationGateResult(gate_id, passed)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "status", ("SCORED", "MANDATORY_GATE_FAILED", "PACK_NOT_READY")
)
def test_direct_public_card_construction_accepts_exact_status_shapes(
    status: str,
) -> None:
    card = EvaluationCard(**_card_kwargs(status))  # type: ignore[arg-type]

    assert card.status == status
    assert card.fixture_origin is True
    assert card.eligible_for_emission is False
    assert card.public_diagnostics == ()
    if status == "SCORED":
        assert card.gate_results[-1].passed is False
        assert card.failure_tags == ()
    elif status == "MANDATORY_GATE_FAILED":
        assert math.copysign(1.0, card.overall_score) == 1.0
        assert any(not gate.passed for gate in card.gate_results)
    else:
        assert card.overall_score is None
        assert card.gate_results == ()


INVALID_PUBLIC_CARD_CASES = (
    "schema-version",
    "schema-version-subclass",
    "result-id",
    "result-id-subclass",
    "status",
    "status-subclass",
    "digest",
    "digest-subclass",
    "overall-int",
    "overall-float-subclass",
    "overall-negative-zero",
    "overall-nan",
    "overall-infinity",
    "components-none",
    "components-subclass",
    "gate-list",
    "gate-tuple-subclass",
    "gate-subclass",
    "duplicate-gates",
    "failure-tag-list",
    "failure-tag-tuple-subclass",
    "failure-tag-unknown",
    "fixture-false",
    "fixture-int",
    "eligible-true",
    "eligible-int",
    "diagnostics-list",
    "diagnostics-tuple-subclass",
    "diagnostics-nonempty",
    "tier",
    "tier-subclass",
    "mandatory-negative-zero",
    "mandatory-nonzero",
    "mandatory-components",
    "mandatory-empty-gates",
    "mandatory-all-pass",
    "mandatory-tags-empty",
    "mandatory-tag-string-subclass",
    "mandatory-tags-extra",
    "unready-overall",
    "unready-components",
    "unready-gates",
    "unready-tags",
)


def _invalid_public_card_kwargs(case: str) -> dict[str, object]:
    status = "SCORED"
    if case.startswith("mandatory-"):
        status = "MANDATORY_GATE_FAILED"
    elif case.startswith("unready-"):
        status = "PACK_NOT_READY"
    values = _card_kwargs(status)

    replacements: dict[str, object] = {
        "schema-version": ("schema_version", "2.0"),
        "schema-version-subclass": (
            "schema_version",
            _StringSubclass("1.0"),
        ),
        "result-id": ("result_id", "not valid"),
        "result-id-subclass": ("result_id", _StringSubclass("result-1.0")),
        "status": ("status", "UNKNOWN"),
        "status-subclass": ("status", _StringSubclass("SCORED")),
        "digest": ("scoring_pack_hash", "sha256:invalid"),
        "digest-subclass": (
            "scoring_pack_hash",
            _StringSubclass(SCORING_DIGEST),
        ),
        "overall-int": ("overall_score", 1),
        "overall-float-subclass": ("overall_score", _FloatSubclass(0.625)),
        "overall-negative-zero": ("overall_score", -0.0),
        "overall-nan": ("overall_score", float("nan")),
        "overall-infinity": ("overall_score", float("inf")),
        "components-none": ("component_scores", None),
        "components-subclass": (
            "component_scores",
            _ComponentScoresSubclass(0.25, 0.5, 0.75),
        ),
        "gate-list": ("gate_results", list(values["gate_results"])),
        "gate-tuple-subclass": (
            "gate_results",
            _TupleSubclass(values["gate_results"]),
        ),
        "gate-subclass": (
            "gate_results",
            (_GateResultSubclass("mandatory_gate", True),),
        ),
        "duplicate-gates": (
            "gate_results",
            (
                EvaluationGateResult("same_gate", True),
                EvaluationGateResult("same_gate", False),
            ),
        ),
        "failure-tag-list": ("failure_tags", []),
        "failure-tag-tuple-subclass": ("failure_tags", _TupleSubclass(())),
        "failure-tag-unknown": ("failure_tags", ("unknown",)),
        "fixture-false": ("fixture_origin", False),
        "fixture-int": ("fixture_origin", 1),
        "eligible-true": ("eligible_for_emission", True),
        "eligible-int": ("eligible_for_emission", 0),
        "diagnostics-list": ("public_diagnostics", []),
        "diagnostics-tuple-subclass": (
            "public_diagnostics",
            _TupleSubclass(()),
        ),
        "diagnostics-nonempty": ("public_diagnostics", ("private",)),
        "tier": ("disclosure_tier", "full"),
        "tier-subclass": (
            "disclosure_tier",
            _StringSubclass("phase0_budgeted"),
        ),
        "mandatory-negative-zero": ("overall_score", -0.0),
        "mandatory-nonzero": ("overall_score", 0.1),
        "mandatory-components": (
            "component_scores",
            EvaluationComponentScores(0.0, 0.0, 0.0),
        ),
        "mandatory-empty-gates": ("gate_results", ()),
        "mandatory-all-pass": (
            "gate_results",
            (EvaluationGateResult("mandatory_gate", True),),
        ),
        "mandatory-tags-empty": ("failure_tags", ()),
        "mandatory-tag-string-subclass": (
            "failure_tags",
            (_StringSubclass("mandatory_gate_failed"),),
        ),
        "mandatory-tags-extra": (
            "failure_tags",
            ("mandatory_gate_failed", "extra"),
        ),
        "unready-overall": ("overall_score", 0.0),
        "unready-components": (
            "component_scores",
            EvaluationComponentScores(0.0, 0.0, 0.0),
        ),
        "unready-gates": (
            "gate_results",
            (EvaluationGateResult("gate", True),),
        ),
        "unready-tags": ("failure_tags", ("mandatory_gate_failed",)),
    }
    field_name, replacement = replacements[case]
    values[field_name] = replacement
    return values


@pytest.mark.parametrize("case", INVALID_PUBLIC_CARD_CASES)
def test_direct_public_card_construction_rejects_invalid_shapes(case: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvaluationCard(**_invalid_public_card_kwargs(case))  # type: ignore[arg-type]


def test_public_types_have_exact_fields_and_are_frozen_slotted_values() -> None:
    assert tuple(field.name for field in fields(EvaluationComponentScores)) == (
        "physics",
        "robustness",
        "accuracy",
    )
    assert tuple(field.name for field in fields(EvaluationGateResult)) == (
        "gate_id",
        "passed",
    )
    assert tuple(field.name for field in fields(EvaluationCard)) == CARD_FIELDS

    values = (
        EvaluationComponentScores(0.25, 0.5, 0.75),
        EvaluationGateResult("gate", True),
        EvaluationCard(**_card_kwargs()),  # type: ignore[arg-type]
    )
    for value in values:
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            value.__setattr__(fields(value)[0].name, None)


def test_first_write_recursively_owns_the_complete_nonempty_a5_graph() -> None:
    store = CardStore()
    record_key = CardRecordKey("record-1.0")
    requester_key = RequesterAuthorizationKey("requester-1.0")
    result = _result()

    disposition = store.write_internal(record_key, requester_key, result)
    private = _single_private_record(store)
    owned = private.internal_result

    assert disposition is CardWriteDisposition.INSERTED
    assert private.record_schema_version == "1.0"
    assert private.record_key == record_key
    assert private.record_key is not record_key
    assert private.requester_authorization_key == requester_key
    assert private.requester_authorization_key is not requester_key
    assert type(owned) is InternalResult
    assert owned == result
    assert owned is not result
    assert owned.pack_pin is not result.pack_pin
    assert owned.pack_pin.challenge_key is not result.pack_pin.challenge_key
    assert owned.gate_decisions is not result.gate_decisions
    assert owned.leg_scores is not result.leg_scores
    for owned_gate, caller_gate in zip(
        owned.gate_decisions, result.gate_decisions, strict=True
    ):
        assert type(owned_gate) is GateDecision
        assert owned_gate == caller_gate
        assert owned_gate is not caller_gate
    for owned_leg, caller_leg in zip(owned.leg_scores, result.leg_scores, strict=True):
        assert type(owned_leg) is LegScore
        assert owned_leg == caller_leg
        assert owned_leg is not caller_leg
        assert owned_leg.components is not caller_leg.components
        for owned_component, caller_component in zip(
            owned_leg.components, caller_leg.components, strict=True
        ):
            assert type(owned_component) is ScalarScore
            assert owned_component == caller_component
            assert owned_component is not caller_component


def test_post_write_recursive_caller_mutation_cannot_change_stored_value() -> None:
    store = CardStore()
    record_key = CardRecordKey("record-1.0")
    requester_key = RequesterAuthorizationKey("requester-1.0")
    result = _result()
    caller_pin = result.pack_pin
    caller_challenge = caller_pin.challenge_key
    caller_gate = result.gate_decisions[0]
    caller_leg = result.leg_scores[0]
    caller_scalar = caller_leg.components[0]

    assert (
        store.write_internal(record_key, requester_key, result)
        is CardWriteDisposition.INSERTED
    )
    expected = store.read_budgeted(
        CardRecordKey("record-1.0"),
        RequesterAuthorizationKey("requester-1.0"),
    )

    object.__setattr__(record_key, "value", "attacker-record")
    object.__setattr__(requester_key, "value", "attacker-requester")
    object.__setattr__(result, "status", ScoreStatus.PACK_NOT_READY)
    object.__setattr__(result, "gate_decisions", ())
    object.__setattr__(result, "leg_scores", ())
    object.__setattr__(result, "combined_score", None)
    object.__setattr__(result, "eligible_for_emission", True)
    object.__setattr__(caller_challenge, "challenge_id", "attacker_challenge")
    object.__setattr__(caller_challenge, "version", "attacker-version")
    object.__setattr__(caller_pin, "scoring_version", "attacker-version")
    object.__setattr__(caller_pin, "scoring_digest", ALTERNATE_SCORING_DIGEST)
    object.__setattr__(caller_pin, "generator_version_required", "attacker-version")
    object.__setattr__(
        caller_pin, "generator_digest_required", ALTERNATE_GENERATOR_DIGEST
    )
    object.__setattr__(caller_pin, "fixture_origin", False)
    object.__setattr__(caller_gate, "gate_id", "attacker_gate")
    object.__setattr__(caller_gate, "passed", False)
    object.__setattr__(caller_gate, "mandatory", False)
    object.__setattr__(caller_leg, "components", ())
    object.__setattr__(caller_leg, "score", 0.0)
    object.__setattr__(caller_scalar, "identifier", "attacker_component")
    object.__setattr__(caller_scalar, "score", 0.0)

    assert (
        store.read_budgeted(
            CardRecordKey("record-1.0"),
            RequesterAuthorizationKey("requester-1.0"),
        )
        == expected
    )
    assert (
        store.write_internal(
            CardRecordKey("record-1.0"),
            RequesterAuthorizationKey("requester-1.0"),
            _result(),
        )
        is CardWriteDisposition.ALREADY_PRESENT
    )
    with pytest.raises(CardAuthorizationError):
        store.read_budgeted(
            CardRecordKey("record-1.0"),
            RequesterAuthorizationKey("attacker-requester"),
        )


def test_forged_exact_type_score_status_pseudo_member_is_rejected() -> None:
    forged = str.__new__(ScoreStatus, "SCORED")
    object.__setattr__(forged, "_name_", "FORGED_SCORED")
    object.__setattr__(forged, "_value_", "SCORED")
    assert type(forged) is ScoreStatus
    assert forged is not ScoreStatus.SCORED
    malformed = _unsafe_copy_exact(_result(), status=forged)
    assert type(malformed) is InternalResult

    with pytest.raises(CardRequestError) as captured:
        CardStore().write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            malformed,  # type: ignore[arg-type]
        )

    _assert_fixed_error(
        captured.value,
        error_type=CardRequestError,
        code="card.request.invalid",
        message="Card request is invalid.",
    )


MALFORMED_A5_CASES = (
    "missing-result-fields",
    "status-type",
    "pin-type",
    "pin-missing-fields",
    "challenge-version",
    "scoring-digest",
    "gate-container",
    "gate-missing-fields",
    "gate-passed",
    "leg-container",
    "component-container",
    "scalar-score",
    "combined-score",
    "eligibility",
)


def _malformed_a5_result(case: str) -> object:
    result = _result()
    if case == "missing-result-fields":
        return object.__new__(InternalResult)
    if case == "status-type":
        return _unsafe_copy_exact(result, status=_StringSubclass("SCORED"))
    if case == "pin-type":
        return _unsafe_copy_exact(result, pack_pin=object())
    if case == "pin-missing-fields":
        return _unsafe_copy_exact(result, pack_pin=object.__new__(ScorePackPin))
    if case == "challenge-version":
        challenge = _unsafe_copy_exact(
            result.pack_pin.challenge_key, version=_HostileString("bad-version")
        )
        pin = _unsafe_copy_exact(result.pack_pin, challenge_key=challenge)
        return _unsafe_copy_exact(result, pack_pin=pin)
    if case == "scoring-digest":
        pin = _unsafe_copy_exact(result.pack_pin, scoring_digest="sha256:invalid")
        return _unsafe_copy_exact(result, pack_pin=pin)
    if case == "gate-container":
        return _unsafe_copy_exact(result, gate_decisions=list(result.gate_decisions))
    if case == "gate-missing-fields":
        return _unsafe_copy_exact(
            result, gate_decisions=(object.__new__(GateDecision),)
        )
    if case == "gate-passed":
        gate = _unsafe_copy_exact(result.gate_decisions[0], passed=1)
        return _unsafe_copy_exact(
            result, gate_decisions=(gate, *result.gate_decisions[1:])
        )
    if case == "leg-container":
        return _unsafe_copy_exact(result, leg_scores=list(result.leg_scores))
    if case == "component-container":
        leg = _unsafe_copy_exact(
            result.leg_scores[0], components=list(result.leg_scores[0].components)
        )
        return _unsafe_copy_exact(result, leg_scores=(leg, *result.leg_scores[1:]))
    if case == "scalar-score":
        scalar = _unsafe_copy_exact(
            result.leg_scores[0].components[0], score=float("nan")
        )
        leg = _unsafe_copy_exact(result.leg_scores[0], components=(scalar,))
        return _unsafe_copy_exact(result, leg_scores=(leg, *result.leg_scores[1:]))
    if case == "combined-score":
        return _unsafe_copy_exact(result, combined_score=float("inf"))
    if case == "eligibility":
        return _unsafe_copy_exact(result, eligible_for_emission=True)
    raise AssertionError("unknown malformed A5 test case")


@pytest.mark.parametrize("case", MALFORMED_A5_CASES)
def test_malformed_exact_a5_instances_fail_closed_without_context(case: str) -> None:
    malformed = _malformed_a5_result(case)

    with pytest.raises(CardRequestError) as captured:
        CardStore().write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            malformed,  # type: ignore[arg-type]
        )

    _assert_fixed_error(
        captured.value,
        error_type=CardRequestError,
        code="card.request.invalid",
        message="Card request is invalid.",
    )


HOSTILE_INPUT_CASES = (
    "record-key-subclass",
    "requester-key-subclass",
    "result-subclass",
    "record-key-value",
    "requester-key-value",
    "pin-subclass",
    "gate-tuple-subclass",
    "gate-id-subclass",
)


@pytest.mark.parametrize("case", HOSTILE_INPUT_CASES)
def test_hostile_hooks_are_not_invoked_before_exact_type_rejection(case: str) -> None:
    record_key: object = CardRecordKey("record")
    requester_key: object = RequesterAuthorizationKey("requester")
    result: object = _result()

    if case == "record-key-subclass":
        record_key = object.__new__(_HostileRecordKey)
    elif case == "requester-key-subclass":
        requester_key = object.__new__(_HostileRequesterKey)
    elif case == "result-subclass":
        result = object.__new__(_HostileInternalResult)
    elif case == "record-key-value":
        object.__setattr__(record_key, "value", _HostileString("record-canary"))
    elif case == "requester-key-value":
        object.__setattr__(requester_key, "value", _HostileString("requester-canary"))
    elif case == "pin-subclass":
        result = _unsafe_copy_exact(
            result, pack_pin=object.__new__(_HostileScorePackPin)
        )
    elif case == "gate-tuple-subclass":
        result = _unsafe_copy_exact(
            result, gate_decisions=_HostileTuple(result.gate_decisions)
        )
    elif case == "gate-id-subclass":
        gate = _unsafe_copy_exact(
            result.gate_decisions[0], gate_id=_HostileString("gate_canary")
        )
        result = _unsafe_copy_exact(
            result, gate_decisions=(gate, *result.gate_decisions[1:])
        )
    else:
        raise AssertionError("unknown hostile test case")

    with pytest.raises(CardRequestError):
        CardStore().write_internal(
            record_key,  # type: ignore[arg-type]
            requester_key,  # type: ignore[arg-type]
            result,  # type: ignore[arg-type]
        )


def test_store_uses_no_generic_copy_serialization_or_introspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_key = CardRecordKey("record")
    requester_key = RequesterAuthorizationKey("requester")
    result = _result()

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("generic copy, serialization, or introspection was used")

    monkeypatch.setattr(copy, "copy", forbidden)
    monkeypatch.setattr(copy, "deepcopy", forbidden)
    monkeypatch.setattr(dataclasses, "asdict", forbidden)
    monkeypatch.setattr(dataclasses, "fields", forbidden)
    monkeypatch.setattr(json, "dumps", forbidden)
    monkeypatch.setattr(pickle, "dumps", forbidden)
    monkeypatch.setattr(builtins, "vars", forbidden)

    store = CardStore()
    assert (
        store.write_internal(record_key, requester_key, result)
        is CardWriteDisposition.INSERTED
    )
    assert store.read_budgeted(record_key, requester_key).status == "SCORED"


def test_store_has_no_private_result_or_mutation_surface_and_repr_is_opaque() -> None:
    requester_canary = "Requester-Repr-Canary"
    result = _result(
        pin=_pin(
            generator_version_required="Private-Generator-Canary",
            generator_digest_required=ALTERNATE_GENERATOR_DIGEST,
        )
    )
    store = CardStore()
    store.write_internal(
        CardRecordKey("Record-Repr-Canary"),
        RequesterAuthorizationKey(requester_canary),
        result,
    )
    private = _single_private_record(store)
    rendered = f"{private!r} {private!s}"

    assert requester_canary not in rendered
    assert "Record-Repr-Canary" not in rendered
    assert "Private-Generator-Canary" not in rendered
    assert ALTERNATE_GENERATOR_DIGEST not in rendered
    assert "InternalResult" not in rendered
    excluded = {
        "get_internal",
        "read_internal",
        "records",
        "list",
        "scan",
        "update",
        "delete",
        "overwrite",
        "rollback",
        "rebind",
        "supersede",
        "serialize",
        "deserialize",
        "save",
        "load",
        "database",
        "receipt",
    }
    assert all(not hasattr(store, name) for name in excluded)
    assert not hasattr(store, "__dict__")


@pytest.mark.parametrize(
    "status",
    (ScoreStatus.SCORED, ScoreStatus.MANDATORY_GATE_FAILED, ScoreStatus.PACK_NOT_READY),
)
def test_exact_duplicate_is_storage_idempotence_for_every_status(
    status: ScoreStatus,
) -> None:
    store = CardStore()
    first = _result(status)
    duplicate = _result(status)

    assert (
        store.write_internal(
            CardRecordKey("record"), RequesterAuthorizationKey("requester"), first
        )
        is CardWriteDisposition.INSERTED
    )
    assert (
        store.write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            duplicate,
        )
        is CardWriteDisposition.ALREADY_PRESENT
    )


def _changed_result(case: str) -> InternalResult:
    result = _result()
    pin = result.pack_pin
    if case == "challenge-id":
        pin = dataclasses.replace(
            pin, challenge_key=ChallengeKey("different_challenge", "fixture-1.0")
        )
    elif case == "challenge-version":
        pin = dataclasses.replace(
            pin, challenge_key=ChallengeKey("a6_fixture", "fixture-2.0")
        )
    elif case == "scoring-version":
        pin = dataclasses.replace(pin, scoring_version="fixture-2.0")
    elif case == "scoring-digest":
        pin = dataclasses.replace(pin, scoring_digest=ALTERNATE_SCORING_DIGEST)
    elif case == "generator-version":
        pin = dataclasses.replace(pin, generator_version_required="fixture-2.0")
    elif case == "generator-digest":
        pin = dataclasses.replace(
            pin, generator_digest_required=ALTERNATE_GENERATOR_DIGEST
        )
    if pin is not result.pack_pin:
        return dataclasses.replace(result, pack_pin=pin)

    gates = result.gate_decisions
    if case == "gate-id":
        gates = (dataclasses.replace(gates[0], gate_id="different_gate"), *gates[1:])
    elif case == "gate-passed":
        gates = (*gates[:-1], dataclasses.replace(gates[-1], passed=True))
    elif case == "gate-mandatory":
        gates = (*gates[:-1], GateDecision("optional_diagnostic", True, True))
    elif case == "gate-order":
        gates = tuple(reversed(gates))
    if gates is not result.gate_decisions:
        return dataclasses.replace(result, gate_decisions=gates)

    legs = result.leg_scores
    if case == "scalar-id":
        scalar = dataclasses.replace(
            legs[0].components[0], identifier="different_component"
        )
        legs = (dataclasses.replace(legs[0], components=(scalar,)), *legs[1:])
    elif case == "scalar-score":
        scalar = dataclasses.replace(legs[0].components[0], score=0.2)
        legs = (dataclasses.replace(legs[0], components=(scalar,)), *legs[1:])
    elif case == "leg-score":
        legs = (dataclasses.replace(legs[0], score=0.2), *legs[1:])
    if legs is not result.leg_scores:
        return dataclasses.replace(result, leg_scores=legs)

    if case == "combined-score":
        return dataclasses.replace(result, combined_score=0.5)
    if case == "status-matrix":
        return _result(ScoreStatus.MANDATORY_GATE_FAILED)
    raise AssertionError("unknown result-difference test case")


@pytest.mark.parametrize(
    "case",
    (
        "challenge-id",
        "challenge-version",
        "scoring-version",
        "scoring-digest",
        "generator-version",
        "generator-digest",
        "gate-id",
        "gate-passed",
        "gate-mandatory",
        "gate-order",
        "scalar-id",
        "scalar-score",
        "leg-score",
        "combined-score",
        "status-matrix",
    ),
)
def test_every_material_valid_result_difference_conflicts_without_overwrite(
    case: str,
) -> None:
    store = CardStore()
    original = _result()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), original
    )
    expected = store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )

    with pytest.raises(CardConflictError) as captured:
        store.write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            _changed_result(case),
        )

    _assert_fixed_error(
        captured.value,
        error_type=CardConflictError,
        code="card.record.conflict",
        message="Card record conflicts with existing data.",
    )
    assert (
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )
        == expected
    )


def test_requester_difference_conflicts_and_preserves_first_binding() -> None:
    store = CardStore()
    result = _result()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester-a"), result
    )

    with pytest.raises(CardConflictError):
        store.write_internal(
            CardRecordKey("record"), RequesterAuthorizationKey("requester-b"), result
        )
    assert (
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester-a")
        ).result_id
        == "record"
    )
    with pytest.raises(CardAuthorizationError):
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester-b")
        )


def test_store_is_per_instance_and_process_local() -> None:
    first = CardStore()
    second = CardStore()
    first.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )

    assert first.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )
    with pytest.raises(CardNotFoundError):
        second.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )


def test_authorization_read_outcomes_are_distinct() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record-a"), RequesterAuthorizationKey("requester-a"), _result()
    )
    store.write_internal(
        CardRecordKey("record-b"), RequesterAuthorizationKey("requester-b"), _result()
    )

    assert (
        store.read_budgeted(
            CardRecordKey("record-a"), RequesterAuthorizationKey("requester-a")
        ).result_id
        == "record-a"
    )
    with pytest.raises(CardNotFoundError) as missing:
        store.read_budgeted(
            CardRecordKey("record-c"), RequesterAuthorizationKey("requester-a")
        )
    _assert_fixed_error(
        missing.value,
        error_type=CardNotFoundError,
        code="card.record.not_found",
        message="Card record was not found.",
    )
    with pytest.raises(CardAuthorizationError) as denied:
        store.read_budgeted(
            CardRecordKey("record-a"), RequesterAuthorizationKey("requester-b")
        )
    _assert_fixed_error(
        denied.value,
        error_type=CardAuthorizationError,
        code="card.authorization.denied",
        message="Card access is not authorized.",
    )


@pytest.mark.parametrize("malformed", ("record", "requester"))
def test_malformed_read_keys_fail_before_lookup(malformed: str) -> None:
    record_key = CardRecordKey("unknown-record")
    requester_key = RequesterAuthorizationKey("unknown-requester")
    if malformed == "record":
        object.__setattr__(record_key, "value", "invalid value")
    else:
        object.__setattr__(requester_key, "value", "invalid value")

    with pytest.raises(CardRequestError):
        CardStore().read_budgeted(record_key, requester_key)


def test_authorization_denial_occurs_before_public_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester-a"), _result()
    )

    def forbidden_projection(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("projection ran before authorization")

    monkeypatch.setattr(store_module, "EvaluationCard", forbidden_projection)
    with pytest.raises(CardAuthorizationError):
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester-b")
        )


def test_exact_private_record_corruption_is_a_bounded_store_error() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    records = store._records  # type: ignore[attr-defined]
    owned_key = next(iter(records))
    records[owned_key] = object()

    with pytest.raises(CardStoreError) as captured:
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )

    _assert_fixed_error(
        captured.value,
        error_type=CardStoreError,
        code="card.store.failure",
        message="Card store operation failed.",
    )


def test_recognized_public_projection_validation_failure_is_bounded() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    private = _single_private_record(store)
    object.__setattr__(private.internal_result, "combined_score", float("nan"))

    with pytest.raises(CardProjectionError) as captured:
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )

    _assert_fixed_error(
        captured.value,
        error_type=CardProjectionError,
        code="card.projection.failure",
        message="Card projection failed.",
    )


def test_arbitrary_projection_runtime_failure_is_not_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )

    def programming_failure(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("programming-failure-canary")

    monkeypatch.setattr(store_module, "EvaluationCard", programming_failure)
    with pytest.raises(RuntimeError, match="programming-failure-canary"):
        store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )


@pytest.mark.parametrize(
    "status",
    (ScoreStatus.SCORED, ScoreStatus.MANDATORY_GATE_FAILED, ScoreStatus.PACK_NOT_READY),
)
def test_exact_status_projection_matrix(status: ScoreStatus) -> None:
    store = CardStore()
    result = _result(status)
    store.write_internal(
        CardRecordKey("record-1.0"),
        RequesterAuthorizationKey("requester-1.0"),
        result,
    )

    card = store.read_budgeted(
        CardRecordKey("record-1.0"), RequesterAuthorizationKey("requester-1.0")
    )

    assert type(card) is EvaluationCard
    assert card.schema_version == "1.0"
    assert card.result_id == "record-1.0"
    assert card.status == status.name
    assert type(card.status) is str
    assert card.scoring_pack_hash == SCORING_DIGEST
    assert card.fixture_origin is True
    assert card.eligible_for_emission is False
    assert card.public_diagnostics == ()
    assert card.disclosure_tier == "phase0_budgeted"
    if status is ScoreStatus.SCORED:
        assert card.overall_score == 0.625
        assert card.component_scores == EvaluationComponentScores(0.25, 0.5, 0.75)
        assert card.gate_results == (
            EvaluationGateResult("mandatory_gate", True),
            EvaluationGateResult("optional_diagnostic", False),
        )
        assert card.failure_tags == ()
    elif status is ScoreStatus.MANDATORY_GATE_FAILED:
        assert card.overall_score == 0.0
        assert math.copysign(1.0, card.overall_score) == 1.0
        assert card.component_scores is None
        assert card.gate_results == (
            EvaluationGateResult("mandatory_gate", False),
            EvaluationGateResult("optional_diagnostic", True),
        )
        assert card.failure_tags == ("mandatory_gate_failed",)
    else:
        assert card.overall_score is None
        assert card.component_scores is None
        assert card.gate_results == ()
        assert card.failure_tags == ()


def test_scored_optional_gate_failure_remains_scored_and_is_not_reclassified() -> None:
    card = EvaluationCard(**_card_kwargs("SCORED"))  # type: ignore[arg-type]
    projected_store = CardStore()
    projected_store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    projected = projected_store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )

    assert card.status == projected.status == "SCORED"
    assert card.gate_results[-1] == projected.gate_results[-1]
    assert card.gate_results[-1].passed is False
    assert card.failure_tags == projected.failure_tags == ()


def test_projection_maps_status_by_identity_not_mutable_enum_value() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    original_value = ScoreStatus.SCORED._value_
    try:
        object.__setattr__(ScoreStatus.SCORED, "_value_", "PRIVATE_STATUS_CANARY")
        card = store.read_budgeted(
            CardRecordKey("record"), RequesterAuthorizationKey("requester")
        )
    finally:
        object.__setattr__(ScoreStatus.SCORED, "_value_", original_value)

    assert card.status == "SCORED"


def test_public_projection_is_allow_listed_and_has_no_private_graph() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    private_record = _single_private_record(store)
    card = store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )
    private_types = (
        CardRecordKey,
        RequesterAuthorizationKey,
        InternalResult,
        ScorePackPin,
        ChallengeKey,
        GateDecision,
        LegScore,
        ScalarScore,
        type(private_record),
    )

    seen: set[int] = set()
    pending = [card]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if value is not card:
            assert not isinstance(value, private_types)
        for referent in gc.get_referents(value):
            if isinstance(referent, (str, bytes, int, float, bool, type)):
                continue
            pending.append(referent)

    assert tuple(field.name for field in fields(card)) == CARD_FIELDS
    assert tuple(field.name for field in fields(card.component_scores)) == (
        "physics",
        "robustness",
        "accuracy",
    )
    assert all(
        tuple(field.name for field in fields(gate)) == ("gate_id", "passed")
        for gate in card.gate_results
    )


def test_private_canaries_and_later_owner_fields_are_absent_from_public_card() -> None:
    private_generator_digest = ALTERNATE_GENERATOR_DIGEST
    private_pin = _pin(
        challenge_key=ChallengeKey("private_challenge", "Private-Challenge-Version"),
        scoring_version="Private-Scoring-Version",
        generator_version_required="Private-Generator-Version",
        generator_digest_required=private_generator_digest,
    )
    private_result = InternalResult(
        status=ScoreStatus.SCORED,
        pack_pin=private_pin,
        gate_decisions=_gate_decisions(),
        leg_scores=_leg_scores(component_prefix="private_scalar_canary"),
        combined_score=0.625,
        eligible_for_emission=False,
    )
    store = CardStore()
    store.write_internal(
        CardRecordKey("public-result"),
        RequesterAuthorizationKey("Private-Requester-Canary"),
        private_result,
    )
    card = store.read_budgeted(
        CardRecordKey("public-result"),
        RequesterAuthorizationKey("Private-Requester-Canary"),
    )
    rendered = repr(card)

    assert card.scoring_pack_hash == SCORING_DIGEST
    assert all(
        canary not in rendered
        for canary in (
            "private_challenge",
            "Private-Challenge-Version",
            "Private-Scoring-Version",
            "Private-Generator-Version",
            private_generator_digest,
            "private_scalar_canary",
            "Private-Requester-Canary",
        )
    )
    forbidden_fields = {
        "requester_authorization_key",
        "record_schema_version",
        "challenge_key",
        "generator_version",
        "generator_digest",
        "numerical_profile",
        "scoring_version",
        "mandatory",
        "threshold",
        "margin",
        "components",
        "scalar_scores",
        "score_input",
        "seed",
        "draw_id",
        "evaluation_binding",
        "strategy",
        "prediction",
        "reference",
        "receipt",
        "evidence",
        "signature",
        "fee",
        "fsm",
        "retry",
        "timestamp",
        "leaderboard",
        "mcp",
    }
    public_field_names = {
        field.name
        for value in (card, card.component_scores, *card.gate_results)
        for field in fields(value)
    }
    assert forbidden_fields.isdisjoint(public_field_names)


def test_repeated_reads_are_distinct_and_mutation_isolated() -> None:
    store = CardStore()
    store.write_internal(
        CardRecordKey("record"), RequesterAuthorizationKey("requester"), _result()
    )
    first = store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )
    second = store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )

    assert first == second
    assert first is not second
    assert first.component_scores is not second.component_scores
    assert first.gate_results is not second.gate_results
    assert all(
        first_gate is not second_gate
        for first_gate, second_gate in zip(
            first.gate_results, second.gate_results, strict=True
        )
    )
    assert tuple(gate.gate_id for gate in first.gate_results) == (
        "mandatory_gate",
        "optional_diagnostic",
    )
    with pytest.raises(FrozenInstanceError):
        first.status = "PACK_NOT_READY"  # type: ignore[misc]

    object.__setattr__(first, "status", "PACK_NOT_READY")
    object.__setattr__(first.component_scores, "physics", 0.0)
    object.__setattr__(first.gate_results[0], "passed", False)
    third = store.read_budgeted(
        CardRecordKey("record"), RequesterAuthorizationKey("requester")
    )

    assert third == second
    assert third.status == "SCORED"
    assert third.component_scores.physics == 0.25
    assert third.gate_results[0].passed is True


def test_cards_public_exports_are_exact_and_exclude_private_a5_types() -> None:
    assert cards.__all__ == PUBLIC_EXPORTS
    assert {name for name in cards.__dict__ if name in PUBLIC_EXPORTS} == set(
        PUBLIC_EXPORTS
    )
    assert not {
        "_StoredCardRecord",
        "InternalResult",
        "ScorePackPin",
        "GateDecision",
        "LegScore",
        "ScalarScore",
        "ScoreStatus",
    }.intersection(cards.__dict__)


def test_cards_import_is_dependency_and_later_owner_isolated(tmp_path: Path) -> None:
    script = f"""
import importlib.abc
import json
import pathlib
import sys

blocked_roots = {{
    "bittensor", "black", "h5py", "jax", "mcp", "neuralop", "neuraloperator",
    "numpy", "pandas", "physicsnemo", "pysr", "pytest", "ruff", "scipy",
    "sklearn", "torch", "yaml",
}}
blocked_carbon = {{
    "carbon.audit", "carbon.backbones", "carbon.chain", "carbon.common",
    "carbon.database", "carbon.db", "carbon.emission", "carbon.evaluation",
    "carbon.evidence", "carbon.execution", "carbon.fees", "carbon.fsm",
    "carbon.leaderboard", "carbon.logging", "carbon.logging_utils", "carbon.mcp",
    "carbon.persistence", "carbon.qualification", "carbon.receipt", "carbon.receipts",
    "carbon.seeding", "carbon.traineval", "carbon.training", "carbon.validator",
}}

def is_blocked(fullname):
    root = fullname.partition(".")[0]
    return root in blocked_roots or any(
        fullname == name or fullname.startswith(name + ".")
        for name in blocked_carbon
    )

class BoundaryBlocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if is_blocked(fullname):
            self.attempted.append(fullname)
            raise ModuleNotFoundError("blocked A6 boundary import", name=fullname)
        return None

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})
blocker = BoundaryBlocker()
sys.meta_path.insert(0, blocker)
import carbon.cards as cards

loaded = sorted(name for name in sys.modules if is_blocked(name))
print(json.dumps({{
    "attempted": blocker.attempted,
    "exports": sorted(cards.__all__),
    "loaded": loaded,
    "module_file": str(pathlib.Path(cards.__file__).resolve()),
}}))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload.pop("module_file") == str(
        (REPOSITORY_ROOT / "carbon/cards/__init__.py").resolve()
    )
    assert payload == {
        "attempted": [],
        "exports": sorted(PUBLIC_EXPORTS),
        "loaded": [],
    }


def _copy_fresh_wheel_source(repository_root: Path, destination: Path) -> None:
    shutil.copy2(repository_root / "pyproject.toml", destination)
    shutil.copy2(repository_root / "README.md", destination)
    shutil.copytree(
        repository_root / "carbon",
        destination / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )


def _offline_wheel_builder() -> str | None:
    candidates = (sys.executable, getattr(sys, "_base_executable", None))
    checked: set[str] = set()
    for candidate in candidates:
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
            return candidate
    return None


def test_fresh_no_dependency_wheel_works_outside_tree_without_later_imports(
    tmp_path: Path,
) -> None:
    build_source = tmp_path / "fresh-source"
    wheelhouse = tmp_path / "wheelhouse"
    environment = tmp_path / "fresh-environment"
    outside_tree = tmp_path / "outside-checkout"
    subprocess_tmp = tmp_path / "subprocess-tmp"
    for directory in (build_source, wheelhouse, outside_tree, subprocess_tmp):
        directory.mkdir()
    _copy_fresh_wheel_source(REPOSITORY_ROOT, build_source)

    process_environment = os.environ.copy()
    process_environment.update(
        {
            "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
            "TMPDIR": str(subprocess_tmp),
        }
    )
    builder = _offline_wheel_builder()
    wheel_command = [
        builder or sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-cache-dir",
        "--no-deps",
        "--wheel-dir",
        str(wheelhouse),
        str(build_source),
    ]
    if builder is not None:
        wheel_command.insert(4, "--no-build-isolation")
        process_environment["PIP_NO_INDEX"] = "1"
    wheel_result = subprocess.run(
        wheel_command,
        cwd=tmp_path,
        env=process_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert wheel_result.returncode == 0, wheel_result.stderr
    wheels = tuple(wheelhouse.glob("carbon-*.whl"))
    assert len(wheels) == 1

    create_result = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        env=process_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert create_result.returncode == 0, create_result.stderr
    environment_python = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    install_environment = process_environment.copy()
    install_environment["PIP_NO_INDEX"] = "1"
    install_result = subprocess.run(
        [
            str(environment_python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-deps",
            "--no-index",
            str(wheels[0]),
        ],
        cwd=outside_tree,
        env=install_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install_result.returncode == 0, install_result.stderr

    script = textwrap.dedent("""
        import dataclasses
        import importlib.abc
        import importlib.metadata
        import json
        import pathlib
        import sys

        blocked_roots = {
            "bittensor", "black", "h5py", "jax", "mcp", "neuralop",
            "neuraloperator", "numpy", "pandas", "physicsnemo", "pysr", "pytest",
            "ruff", "scipy", "sklearn", "torch", "yaml",
        }
        blocked_carbon = {
            "carbon.audit", "carbon.backbones", "carbon.chain", "carbon.common",
            "carbon.database", "carbon.db", "carbon.emission", "carbon.evaluation",
            "carbon.evidence", "carbon.execution", "carbon.fees", "carbon.fsm",
            "carbon.leaderboard", "carbon.logging", "carbon.logging_utils", "carbon.mcp",
            "carbon.persistence", "carbon.qualification", "carbon.receipt",
            "carbon.receipts", "carbon.seeding", "carbon.traineval", "carbon.training",
            "carbon.validator",
        }

        def is_blocked(fullname):
            root = fullname.partition(".")[0]
            return root in blocked_roots or any(
                fullname == name or fullname.startswith(name + ".")
                for name in blocked_carbon
            )

        class BoundaryBlocker(importlib.abc.MetaPathFinder):
            def __init__(self):
                self.attempted = []

            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if is_blocked(fullname):
                    self.attempted.append(fullname)
                    raise ModuleNotFoundError("blocked A6 wheel import", name=fullname)
                return None

        blocker = BoundaryBlocker()
        sys.meta_path.insert(0, blocker)

        import carbon.cards as cards
        from carbon.cards import (
            CardRecordKey,
            CardStore,
            CardWriteDisposition,
            RequesterAuthorizationKey,
        )
        from carbon.registry import ChallengeKey
        from carbon.scoring.model import (
            GateDecision,
            InternalResult,
            LegScore,
            ScalarScore,
            ScorePackPin,
            ScoreStatus,
        )

        pin = ScorePackPin(
            challenge_key=ChallengeKey("a6_fixture", "fixture-1.0"),
            scoring_version="fixture-1.0",
            scoring_digest="sha256:" + "a" * 64,
            generator_version_required="fixture-1.0",
            generator_digest_required="sha256:" + "b" * 64,
            schema_version="1.0",
            numerical_profile="python_binary64_v1",
            fixture_origin=True,
        )
        legs = tuple(
            LegScore(leg, (ScalarScore(leg + "_private", 0.125),), score)
            for leg, score in (
                ("physics", 0.25),
                ("robustness", 0.5),
                ("accuracy", 0.75),
            )
        )
        result = InternalResult(
            status=ScoreStatus.SCORED,
            pack_pin=pin,
            gate_decisions=(
                GateDecision("mandatory_gate", True, True),
                GateDecision("optional_diagnostic", False, False),
            ),
            leg_scores=legs,
            combined_score=0.625,
            eligible_for_emission=False,
        )
        store = CardStore()
        inserted = store.write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            result,
        )
        duplicate = store.write_internal(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
            result,
        )
        card = store.read_budgeted(
            CardRecordKey("record"),
            RequesterAuthorizationKey("requester"),
        )
        distribution = importlib.metadata.distribution("carbon")
        loaded = sorted(name for name in sys.modules if is_blocked(name))
        print(json.dumps({
            "attempted": blocker.attempted,
            "card_fields": [field.name for field in dataclasses.fields(card)],
            "components": [
                card.component_scores.physics,
                card.component_scores.robustness,
                card.component_scores.accuracy,
            ],
            "dispositions": [inserted.value, duplicate.value],
            "distribution": [distribution.metadata["Name"], distribution.version],
            "exports": sorted(cards.__all__),
            "gates": [[gate.gate_id, gate.passed] for gate in card.gate_results],
            "loaded": loaded,
            "module_file": str(pathlib.Path(cards.__file__).resolve()),
            "status": card.status,
            "write_members_canonical": [
                inserted is CardWriteDisposition.INSERTED,
                duplicate is CardWriteDisposition.ALREADY_PRESENT,
            ],
        }, sort_keys=True))
        """)
    execution_result = subprocess.run(
        [str(environment_python), "-I", "-c", script],
        cwd=outside_tree,
        env=install_environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert execution_result.returncode == 0, execution_result.stderr
    payload = json.loads(execution_result.stdout)
    module_file = Path(payload.pop("module_file"))
    assert REPOSITORY_ROOT not in module_file.parents
    assert build_source not in module_file.parents
    assert outside_tree not in module_file.parents
    assert environment in module_file.parents
    assert payload == {
        "attempted": [],
        "card_fields": list(CARD_FIELDS),
        "components": [0.25, 0.5, 0.75],
        "dispositions": ["INSERTED", "ALREADY_PRESENT"],
        "distribution": ["carbon", "0.9.0"],
        "exports": sorted(PUBLIC_EXPORTS),
        "gates": [["mandatory_gate", True], ["optional_diagnostic", False]],
        "loaded": [],
        "status": "SCORED",
        "write_members_canonical": [True, True],
    }
