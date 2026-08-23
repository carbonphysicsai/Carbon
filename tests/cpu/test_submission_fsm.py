"""CPU acceptance tests for A7 submission identity, fees, and the closed FSM."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import os
import pickle
import shutil
import struct
import subprocess
import sys
import textwrap
import threading
import uuid
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from typing import Any

import pytest

from carbon import fees
from carbon.cards import (
    CardConflictError,
    CardRecordKey,
    CardStore,
    CardStoreError,
    EvaluationCard,
    RequesterAuthorizationKey,
)
from carbon.fees import (
    AdmissionKind,
    AttemptEvent,
    AttemptEventKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeEventKind,
    FeeOperationContext,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    InitialRunStartResult,
    RequesterIdentity,
    StartDisposition,
    StrategyHash,
    SubmissionAdmissionError,
    SubmissionAuthorizationError,
    SubmissionConflictError,
    SubmissionId,
    SubmissionIntegrationError,
    SubmissionNotFoundError,
    SubmissionRequestError,
    SubmissionResourceError,
    SubmissionResourceLimits,
    SubmissionResourcePolicyError,
    SubmissionService,
    SubmissionState,
    SubmissionStateError,
    SubmissionStatusView,
    SubmissionStoreError,
)
from carbon.fees import identity as identity_module
from carbon.fees import service as service_module
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationEvidence,
    QualificationManifest,
    RegistryError,
)
from carbon.scoring import ScoreEngine
from carbon.scoring.model import (
    GateDecision,
    InternalResult,
    LegScore,
    ScalarScore,
    ScoreInput,
    ScorePackPin,
    ScoreStatus,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "a7_fixture"
CHALLENGE_VERSION = "fixture-1.0"
CHALLENGE_KEY = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
REQUESTER = RequesterIdentity("fixture-requester-v1")
OTHER_REQUESTER = RequesterIdentity("fixture-other-requester-v1")
GENERATOR_VERSION = "fixture-generator-v1.0"
SCORING_VERSION = "fixture-scoring-v1.0"
GENERATOR_DIGEST = "sha256:" + "a" * 64
SCORING_DIGEST = "sha256:" + "b" * 64
CONTAINER_DIGEST = "sha256:" + "c" * 64
FEE_POLICY_KEY = FeePolicyKey("fixture-fee-policy-v1.0")
FIXTURE_AMOUNT = 1703

PUBLIC_EXPORTS = (
    "AdmissionKind",
    "AttemptEvent",
    "AttemptEventKind",
    "ExecutionAttemptHandle",
    "ExecutionEnvironmentPin",
    "FeeEvent",
    "FeeEventKind",
    "FeeOperationContext",
    "FeeOperationKey",
    "FeePolicyKey",
    "FixtureExecutionEnvelope",
    "FixtureSubmissionPolicy",
    "InitialRunStartResult",
    "ProductionExecutionEnvelope",
    "RequesterIdentity",
    "StartDisposition",
    "StrategyHash",
    "SubmissionAdmissionError",
    "SubmissionAuthorizationError",
    "SubmissionConflictError",
    "SubmissionId",
    "SubmissionIntegrationError",
    "SubmissionNotFoundError",
    "SubmissionRequestError",
    "SubmissionResourceError",
    "SubmissionResourceLimits",
    "SubmissionResourcePolicyError",
    "SubmissionService",
    "SubmissionState",
    "SubmissionStateError",
    "SubmissionStatusView",
    "SubmissionStoreError",
)


class _StringSubclass(str):
    pass


class _IntegerSubclass(int):
    pass


class _HostileObject:
    """Object whose Python protocol hooks must not run during Strategy capture."""

    def __init__(self) -> None:
        self.armed = False

    def __hash__(self) -> int:
        if self.armed:
            raise AssertionError("hostile hash was invoked")
        return 1729

    def __eq__(self, other: object) -> bool:
        del other
        if self.armed:
            raise AssertionError("hostile equality was invoked")
        return False

    def __repr__(self) -> str:
        raise AssertionError("hostile repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile str was invoked")


class _HostileLeaf:
    def __repr__(self) -> str:
        raise AssertionError("hostile repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile str was invoked")

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile hash was invoked")


class _HostileHandleField:
    def __getattribute__(self, name: str) -> object:
        del name
        raise RuntimeError("private-hostile-handle-canary")


class _ObservedSlot:
    """Count reads from one exact slotted source while preserving construction."""

    def __init__(self, original: object, target: object) -> None:
        self.original = original
        self.target = target
        self.reads = 0

    def __get__(self, instance: object, owner: type[object]) -> object:
        if instance is None:
            return self
        if instance is self.target:
            self.reads += 1
        return self.original.__get__(instance, owner)  # type: ignore[attr-defined]

    def __set__(self, instance: object, value: object) -> None:
        self.original.__set__(instance, value)  # type: ignore[attr-defined]


def _limits(**overrides: object) -> SubmissionResourceLimits:
    values: dict[str, object] = {
        "max_total_value_nodes": 10_000,
        "max_object_members": 256,
        "max_list_items": 256,
        "max_string_utf8_bytes": 4096,
        "max_object_key_utf8_bytes": 512,
        "max_strategy_identity_bytes": 1_000_000,
        "max_challenge_id_bytes": 256,
        "max_concurrent_identity_builds": 8,
        "max_retained_submission_records": 256,
        "max_retained_value_nodes": 1_000_000,
        "max_retained_strategy_identity_bytes": 16_000_000,
    }
    values.update(overrides)
    return SubmissionResourceLimits(**values)  # type: ignore[arg-type]


def _strategy(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": "fno",
        "parameters": {
            "fixture_note": "deliberately_non_scientific",
            "layers": [1, 2, 3],
        },
    }
    value.update(overrides)
    return value


def _independent_frame(value: object) -> bytes:
    """Small independent A7-R3 oracle; it calls no A7 encoder helper."""
    value_type = type(value)
    if value is None:
        tag = 0x00
        payload = b""
    elif value_type is bool:
        tag = 0x02 if value else 0x01
        payload = b""
    elif value_type is int:
        tag = 0x03
        integer = int(value)
        magnitude_value = abs(integer)
        magnitude = magnitude_value.to_bytes(
            (magnitude_value.bit_length() + 7) // 8,
            "big",
        )
        payload = bytes((0x01 if integer < 0 else 0x00,)) + magnitude
    elif value_type is float:
        tag = 0x04
        payload = struct.pack(">d", value)
    elif value_type is str:
        tag = 0x05
        payload = value.encode("utf-8", errors="strict")
    elif value_type is list:
        tag = 0x06
        payload = len(value).to_bytes(8, "big") + b"".join(
            _independent_frame(item) for item in value
        )
    elif value_type is dict:
        tag = 0x07
        items = sorted(value.items(), key=lambda item: item[0].encode("utf-8"))
        payload = len(items).to_bytes(8, "big") + b"".join(
            _independent_frame(key) + _independent_frame(item) for key, item in items
        )
    else:  # pragma: no cover - the oracle is used only for valid JSON values
        raise TypeError("independent oracle received an unsupported value")
    return bytes((tag,)) + len(payload).to_bytes(8, "big") + payload


def _independent_strategy_hash(strategy: dict[str, object]) -> str:
    preimage = b"carbon.strategy.identity.v1" + _independent_frame(strategy)
    return "sha256:" + hashlib.sha256(preimage).hexdigest()


def _independent_binding(
    submission_id: SubmissionId,
    strategy_hash: StrategyHash,
    challenge_key: ChallengeKey,
) -> bytes:
    fields_to_frame = (
        (0x01, submission_id.value),
        (0x02, strategy_hash.value),
        (0x03, challenge_key.challenge_id),
        (0x04, challenge_key.version),
    )
    document = bytearray(b"carbon.a7.evaluation-binding.v1")
    for tag, value in fields_to_frame:
        payload = value.encode("ascii", errors="strict")
        document.extend(bytes((tag,)))
        document.extend(len(payload).to_bytes(4, "big"))
        document.extend(payload)
    return hashlib.sha256(document).digest()


def _fixture_registry(tmp_path: Path) -> ChallengeRegistry:
    registry_root = tmp_path / "registry"
    artifact_root = tmp_path / "artifacts"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(
        registry_root,
        artifact_root,
    )
    artifact_id = "fixture_bundle"
    artifact_path = f"{CHALLENGE_ID}/{CHALLENGE_VERSION}/fixture/bundle.bin"
    content = b"A7 conspicuous non-scientific fixture artifact\n"
    target = registry.artifact_root.joinpath(*artifact_path.split("/"))
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    artifact_digest = "sha256:" + hashlib.sha256(content).hexdigest()
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a7-fixture-only-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    registry.save(
        ChallengeRecord(
            challenge_id=CHALLENGE_ID,
            version=CHALLENGE_VERSION,
            fixture_origin=True,
            status="fixture",
            allowed_backbones=("fno",),
            artifacts={
                artifact_id: ArtifactBinding(
                    path=artifact_path,
                    digest=artifact_digest,
                )
            },
            qualification=QualificationManifest(
                challenge_id=CHALLENGE_ID,
                challenge_version=CHALLENGE_VERSION,
                mode="fixture",
                slots=slots,
            ),
        )
    )
    assert registry.assess_live_eligibility(
        CHALLENGE_ID,
        CHALLENGE_VERSION,
        fixture_mode=True,
    ).eligible
    return registry


def _production_registry(
    tmp_path: Path,
    *,
    allowed_backbones: tuple[str, ...] = ("fno",),
) -> ChallengeRegistry:
    registry_root = tmp_path / "production-registry"
    artifact_root = tmp_path / "production-artifacts"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(
        registry_root,
        artifact_root,
    )
    artifact_id = "qualified_bundle"
    artifact_path = f"{CHALLENGE_ID}/{CHALLENGE_VERSION}/qualified/bundle.bin"
    content = b"A7 structural production-gate fixture; no production execution\n"
    target = registry.artifact_root.joinpath(*artifact_path.split("/"))
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    artifact_digest = "sha256:" + hashlib.sha256(content).hexdigest()
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a7-structural-gate-test-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    record = ChallengeRecord(
        challenge_id=CHALLENGE_ID,
        version=CHALLENGE_VERSION,
        fixture_origin=False,
        status="draft",
        allowed_backbones=allowed_backbones,
        artifacts={
            artifact_id: ArtifactBinding(
                path=artifact_path,
                digest=artifact_digest,
            )
        },
        qualification=QualificationManifest(
            challenge_id=CHALLENGE_ID,
            challenge_version=CHALLENGE_VERSION,
            mode="production",
            slots=slots,
        ),
    )
    registry.save(record)
    registry.activate_live(CHALLENGE_ID, CHALLENGE_VERSION)
    assert registry.is_effectively_live(CHALLENGE_ID, CHALLENGE_VERSION)
    return registry


def _environment_pin() -> ExecutionEnvironmentPin:
    return ExecutionEnvironmentPin(
        backend_profile_id="fixture-backend-profile-v1.0",
        container_digest=CONTAINER_DIGEST,
    )


def _fixture_policy(**overrides: object) -> FixtureSubmissionPolicy:
    values: dict[str, object] = {
        "fee_policy_key": FEE_POLICY_KEY,
        "amount_minor": FIXTURE_AMOUNT,
        "max_attempts": 2,
        "generator_version": GENERATOR_VERSION,
        "generator_digest": GENERATOR_DIGEST,
        "scoring_version": SCORING_VERSION,
        "scoring_digest": SCORING_DIGEST,
        "environment_pin": _environment_pin(),
    }
    values.update(overrides)
    return FixtureSubmissionPolicy(**values)  # type: ignore[arg-type]


def _service(
    tmp_path: Path,
    *,
    limits: SubmissionResourceLimits | None = None,
    policy: FixtureSubmissionPolicy | None = None,
    registry: ChallengeRegistry | None = None,
    uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    card_store_seed: (
        tuple[CardRecordKey, RequesterAuthorizationKey, InternalResult] | None
    ) = None,
) -> SubmissionService:
    return SubmissionService(
        resource_limits=limits or _limits(),
        registry=registry or _fixture_registry(tmp_path),
        fixture_policy=policy or _fixture_policy(),
        _uuid_factory=uuid_factory,
        _card_store_seed=card_store_seed,
    )


def _score_pack_pin(
    *,
    challenge_key: ChallengeKey = CHALLENGE_KEY,
    scoring_version: str = SCORING_VERSION,
    scoring_digest: str = SCORING_DIGEST,
    generator_version: str = GENERATOR_VERSION,
    generator_digest: str = GENERATOR_DIGEST,
) -> ScorePackPin:
    return ScorePackPin(
        challenge_key=challenge_key,
        scoring_version=scoring_version,
        scoring_digest=scoring_digest,
        generator_version_required=generator_version,
        generator_digest_required=generator_digest,
        schema_version="1.0",
        numerical_profile="python_binary64_v1",
        fixture_origin=True,
    )


def _result(
    status: ScoreStatus = ScoreStatus.SCORED,
    *,
    pin: ScorePackPin | None = None,
) -> InternalResult:
    pack_pin = pin or _score_pack_pin()
    if status is ScoreStatus.PACK_NOT_READY:
        return InternalResult(
            status=status,
            pack_pin=pack_pin,
            gate_decisions=(),
            leg_scores=(),
            combined_score=None,
            eligible_for_emission=False,
        )
    if status is ScoreStatus.MANDATORY_GATE_FAILED:
        return InternalResult(
            status=status,
            pack_pin=pack_pin,
            gate_decisions=(GateDecision("fixture_gate", False, True),),
            leg_scores=(),
            combined_score=0.0,
            eligible_for_emission=False,
        )
    legs = tuple(
        LegScore(
            leg=leg,
            components=(ScalarScore(f"fixture_{leg}", score),),
            score=score,
        )
        for leg, score in (
            ("physics", 0.25),
            ("robustness", 0.5),
            ("accuracy", 0.75),
        )
    )
    return InternalResult(
        status=status,
        pack_pin=pack_pin,
        gate_decisions=(GateDecision("fixture_gate", True, True),),
        leg_scores=legs,
        combined_score=0.5,
        eligible_for_emission=False,
    )


def _accepted_identity(
    strategy: dict[str, object] | None = None,
    limits: SubmissionResourceLimits | None = None,
) -> Any:
    result = identity_module._validate_and_hash_strategy(
        strategy or _strategy(),
        limits or _limits(),
    )
    assert result.validation is not None and result.validation.ok
    assert result.strategy is not None
    assert result.strategy_hash is not None
    assert result.a7_error_code is None
    return result


def _submit_validate_admit(service: SubmissionService) -> SubmissionId:
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)
    service.admit_fixture(submission_id, REQUESTER)
    return submission_id


def _start(
    service: SubmissionService,
    submission_id: SubmissionId,
    *,
    charge: str = "fixture-charge-op-v1",
    refund: str = "fixture-refund-op-v1",
) -> InitialRunStartResult:
    return service.start_fixture_attempt(
        submission_id,
        REQUESTER,
        FeeOperationKey(charge),
        FeeOperationKey(refund),
    )


def _record(service: SubmissionService, submission_id: SubmissionId) -> Any:
    """Focused tests inspect private invariants without widening the public API."""
    return service._store.records[submission_id.value]


def _lifecycle_snapshot(
    service: SubmissionService,
    submission_id: SubmissionId,
) -> tuple[object, ...]:
    record = _record(service, submission_id)
    return (
        record.state,
        record.admission_kind,
        record.seed_pin,
        record.environment_pin,
        record.attempt_number,
        record.current_handle,
        record.terminal_infra_disposition,
        record.terminal_infra_operation_key,
        tuple(record.attempt_events),
        tuple(record.fee_events),
        tuple(sorted(service._store.open_index.items())),
        service._store.retained_value_nodes,
        service._store.retained_strategy_identity_bytes,
    )


@pytest.mark.parametrize(
    ("nominal", "valid"),
    (
        (RequesterIdentity, "requester-v1"),
        (FeePolicyKey, "fee-policy-v1.0"),
        (FeeOperationKey, "operation-v1.0"),
    ),
)
def test_token_nominals_are_exact_frozen_slotted_and_non_normalizing(
    nominal: type[object],
    valid: str,
) -> None:
    value = nominal(valid)

    assert value.value == valid  # type: ignore[attr-defined]
    assert not hasattr(value, "__dict__")
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        value.value = "changed"  # type: ignore[attr-defined,misc]
    for invalid in ("", " leading", "trailing ", "bad/token", "x" * 65):
        with pytest.raises((TypeError, ValueError)):
            nominal(invalid)
    with pytest.raises((TypeError, ValueError)):
        nominal(_StringSubclass(valid))


@pytest.mark.parametrize(
    ("nominal", "valid"),
    (
        (SubmissionId, "123e4567-e89b-42d3-a456-426614174000"),
        (StrategyHash, "sha256:" + "a" * 64),
        (RequesterIdentity, "requester-v1"),
        (FeePolicyKey, "fee-policy-v1.0"),
        (FeeOperationKey, "operation-v1.0"),
    ),
)
def test_all_five_a7_nominals_are_frozen_and_slotted(
    nominal: type[object],
    valid: str,
) -> None:
    value = nominal(valid)

    assert not hasattr(value, "__dict__")
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        value.value = valid  # type: ignore[attr-defined,misc]


def test_nominal_types_are_not_interchangeable() -> None:
    assert RequesterIdentity("same") != FeePolicyKey("same")
    assert FeePolicyKey("same") != FeeOperationKey("same")
    assert FeeOperationKey("same") != RequesterIdentity("same")


@pytest.mark.parametrize(
    "value",
    (
        "550e8400-e29b-11d4-a716-446655440000",
        "550E8400-E29B-41D4-A716-446655440000",
        "{550e8400-e29b-41d4-a716-446655440000}",
        "550e8400e29b41d4a716446655440000",
        _StringSubclass("550e8400-e29b-41d4-a716-446655440000"),
    ),
)
def test_submission_id_rejects_noncanonical_or_non_v4_text(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SubmissionId(value)  # type: ignore[arg-type]


def test_submission_id_accepts_only_canonical_uuid4() -> None:
    text = "123e4567-e89b-42d3-a456-426614174000"
    submission_id = SubmissionId(text)

    assert submission_id.value == text
    assert str(uuid.UUID(submission_id.value)) == text
    assert uuid.UUID(submission_id.value).version == 4


@pytest.mark.parametrize(
    "value",
    (
        "sha256:" + "a" * 63,
        "sha256:" + "A" * 64,
        "sha512:" + "a" * 64,
        _StringSubclass("sha256:" + "a" * 64),
    ),
)
def test_strategy_hash_rejects_noncanonical_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        StrategyHash(value)  # type: ignore[arg-type]


def test_closed_enums_have_exact_members() -> None:
    assert {member.value for member in AdmissionKind} == {"PRODUCTION", "FIXTURE"}
    assert {member.value for member in SubmissionState} == {
        "RECEIVED",
        "VALIDATED",
        "QUEUED",
        "RUNNING",
        "SCORED",
        "PUBLISHED",
        "REJECTED",
        "FAILED_INFRA",
        "FAILED_STRATEGY",
        "CANCELLED",
    }
    assert {member.value for member in AttemptEventKind} == {
        "QUEUED",
        "RUNNING",
        "RETRYABLE_INFRA",
        "SCORED",
        "FAILED_STRATEGY",
        "FAILED_INFRA",
        "CANCELLED",
    }
    assert {member.value for member in FeeEventKind} == {
        "CHARGE",
        "REFUND",
        "RETRY_CREDIT",
    }
    assert {member.value for member in FeeOperationContext} == {
        "INITIAL_RUN_START",
        "RETRY",
        "TERMINAL_INFRA",
        "PUBLICATION_INFRA",
    }
    assert {member.value for member in StartDisposition} == {
        "STARTED",
        "ALREADY_STARTED",
    }


LIMIT_FIELDS = (
    "max_total_value_nodes",
    "max_object_members",
    "max_list_items",
    "max_string_utf8_bytes",
    "max_object_key_utf8_bytes",
    "max_strategy_identity_bytes",
    "max_challenge_id_bytes",
    "max_concurrent_identity_builds",
    "max_retained_submission_records",
    "max_retained_value_nodes",
    "max_retained_strategy_identity_bytes",
)


def test_resource_limits_are_exact_immutable_and_have_no_defaults() -> None:
    limits = _limits()

    assert tuple(field.name for field in fields(limits)) == LIMIT_FIELDS
    assert not hasattr(limits, "__dict__")
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        limits.max_total_value_nodes = 2  # type: ignore[misc]
    with pytest.raises(TypeError):
        SubmissionResourceLimits()  # type: ignore[call-arg]


@pytest.mark.parametrize("field_name", LIMIT_FIELDS)
@pytest.mark.parametrize("invalid", (0, -1, True, 1.0, "1", None, 2**64))
def test_each_resource_limit_rejects_invalid_exact_values(
    field_name: str,
    invalid: object,
) -> None:
    values = {field.name: getattr(_limits(), field.name) for field in fields(_limits())}
    values[field_name] = invalid

    with pytest.raises(SubmissionResourcePolicyError) as caught:
        SubmissionResourceLimits(**values)
    assert caught.value.code == "submission.resource_policy_unavailable"
    assert str(caught.value) == "Submission resource policy is unavailable."
    assert field_name not in str(caught.value)
    assert str(invalid) not in str(caught.value)


def test_challenge_limit_has_unsigned_32_ceiling() -> None:
    assert _limits(max_challenge_id_bytes=2**32 - 1).max_challenge_id_bytes == 2**32 - 1
    with pytest.raises(SubmissionResourcePolicyError):
        _limits(max_challenge_id_bytes=2**32)


@pytest.mark.parametrize("invalid", (True, -1, 1.5, "17", 2**64))
def test_fixture_fee_amount_rejects_non_exact_nonnegative_integer(
    invalid: object,
) -> None:
    with pytest.raises((TypeError, ValueError, SubmissionAdmissionError)):
        _fixture_policy(amount_minor=invalid)


def test_fixture_fee_amount_zero_is_representable() -> None:
    assert _fixture_policy(amount_minor=0).amount_minor == 0
    assert _fixture_policy(amount_minor=2**64 - 1).amount_minor == 2**64 - 1


@pytest.mark.parametrize("invalid", (0, -1, True, 1.0, "2"))
def test_retry_attempt_budget_is_exact_positive_integer(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError, SubmissionAdmissionError)):
        _fixture_policy(max_attempts=invalid)


@pytest.mark.parametrize(
    ("profile", "digest"),
    (
        ("", CONTAINER_DIGEST),
        ("bad/profile", CONTAINER_DIGEST),
        ("x" * 129, CONTAINER_DIGEST),
        (_StringSubclass("profile"), CONTAINER_DIGEST),
        ("profile", "sha256:" + "A" * 64),
        ("profile", _StringSubclass(CONTAINER_DIGEST)),
    ),
)
def test_execution_environment_pin_is_exact_and_bounded(
    profile: object,
    digest: object,
) -> None:
    with pytest.raises((TypeError, ValueError, SubmissionIntegrationError)):
        ExecutionEnvironmentPin(profile, digest)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "strategy",
    (
        _strategy(),
        _strategy(parameters={}),
        _strategy(parameters={"empty": [], "object": {}}),
        _strategy(parameters={"integer": 0, "negative": -257}),
        _strategy(parameters={"float": -0.0, "unicode": "Ω\U0001f680"}),
        _strategy(parameters={"nested": [{"z": None, "a": [False, True]}]}),
        _strategy(parameters={"large": (1 << 521) + 17}),
    ),
)
def test_strategy_hash_matches_independent_golden_encoder(
    strategy: dict[str, object],
) -> None:
    result = _accepted_identity(strategy)

    assert result.strategy_hash.value == _independent_strategy_hash(strategy)
    assert result.identity_bytes == len(
        b"carbon.strategy.identity.v1" + _independent_frame(strategy)
    )


def test_object_insertion_order_does_not_change_hash() -> None:
    first = _strategy(parameters={"z": 1, "a": 2, "ä": 3})
    second = _strategy(parameters={"ä": 3, "a": 2, "z": 1})

    assert (
        _accepted_identity(first).strategy_hash
        == _accepted_identity(second).strategy_hash
    )


@pytest.mark.parametrize(
    ("left", "right"),
    (
        (1, 1.0),
        (0.0, -0.0),
        ([1, 2], [2, 1]),
        (False, 0),
        (None, ""),
        ("e\u0301", "é"),
        (2**80, 2**80 + 1),
    ),
)
def test_hash_distinguishes_type_order_binary_and_unicode_perturbations(
    left: object,
    right: object,
) -> None:
    first = _accepted_identity(_strategy(parameters={"value": left})).strategy_hash
    second = _accepted_identity(_strategy(parameters={"value": right})).strategy_hash

    assert first != second


def test_hash_is_identical_under_distinct_sufficient_policies() -> None:
    strategy = _strategy(parameters={"nested": [1, {"k": "v"}]})
    exact = _accepted_identity(strategy)
    larger = _accepted_identity(
        strategy,
        _limits(
            max_total_value_nodes=20_000,
            max_strategy_identity_bytes=2_000_000,
        ),
    )

    assert exact.strategy_hash == larger.strategy_hash
    assert exact.identity_bytes == larger.identity_bytes


def test_cycle_reaches_a2_with_exact_cycle_issue() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    result = identity_module._validate_and_hash_strategy(
        _strategy(parameters={"cycle": cyclic}),
        _limits(),
    )

    assert result.strategy is None
    assert result.strategy_hash is None
    assert result.a7_error_code is None
    assert result.validation is not None
    assert [(issue.code, issue.path) for issue in result.validation.errors] == [
        ("json.cycle", "/parameters/cycle/0")
    ]


def test_shared_dag_is_a2_valid_then_rejected_by_a7() -> None:
    shared: list[object] = [1, 2]
    strategy = _strategy(parameters={"left": shared, "right": shared})

    result = identity_module._validate_and_hash_strategy(strategy, _limits())

    assert result.validation is not None and result.validation.ok
    assert result.a7_error_code == "strategy.alias_forbidden"
    assert result.strategy is None
    assert result.strategy_hash is None


def test_lone_surrogate_reaches_a2_before_a7_utf8_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = identity_module.strategy_schema.dry_validate
    calls: list[object] = []

    def spy(value: object) -> object:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(identity_module.strategy_schema, "dry_validate", spy)
    result = identity_module._validate_and_hash_strategy(
        _strategy(parameters={"text": "\ud800"}),
        _limits(),
    )

    assert len(calls) == 1
    assert result.validation is not None and result.validation.ok
    assert result.a7_error_code == "strategy.utf8_invalid"
    assert result.strategy_hash is None


def test_hostile_key_is_never_invoked_and_preserves_a2_key_issue() -> None:
    hostile = _HostileObject()
    parameters: dict[object, object] = {hostile: "value"}
    hostile.armed = True

    result = identity_module._validate_and_hash_strategy(
        _strategy(parameters=parameters),
        _limits(),
    )

    assert result.validation is not None
    assert [(issue.code, issue.path) for issue in result.validation.errors] == [
        ("json.key_type", "/parameters")
    ]
    assert result.strategy is None
    assert result.strategy_hash is None


def test_hostile_leaf_is_never_invoked_and_preserves_a2_value_issue() -> None:
    result = identity_module._validate_and_hash_strategy(
        _strategy(parameters={"leaf": _HostileLeaf()}),
        _limits(),
    )

    assert result.validation is not None
    assert [(issue.code, issue.path) for issue in result.validation.errors] == [
        ("json.value_type", "/parameters/leaf")
    ]
    assert result.strategy is None
    assert result.strategy_hash is None


@pytest.mark.parametrize("value", (_IntegerSubclass(1), _StringSubclass("value")))
def test_json_scalar_subclasses_are_not_coerced_or_accepted(value: object) -> None:
    result = identity_module._validate_and_hash_strategy(
        _strategy(parameters={"value": value}),
        _limits(),
    )

    assert result.validation is not None
    assert [(issue.code, issue.path) for issue in result.validation.errors] == [
        ("json.value_type", "/parameters/value")
    ]
    assert result.strategy is None
    assert result.strategy_hash is None


def test_deep_allowed_strategy_is_captured_hashed_and_copied_iteratively() -> None:
    root: list[object] = []
    cursor = root
    for _ in range(1500):
        child: list[object] = []
        cursor.append(child)
        cursor = child
    strategy = _strategy(parameters={"deep": root})

    result = _accepted_identity(
        strategy,
        _limits(max_total_value_nodes=2000, max_strategy_identity_bytes=100_000),
    )
    copied = identity_module._copy_strategy_tree(result.strategy)

    assert copied is not result.strategy
    assert copied["parameters"] is not result.strategy["parameters"]
    depth = 0
    value = copied["parameters"]["deep"]  # type: ignore[index]
    while value:
        depth += 1
        value = value[0]  # type: ignore[index]
    assert depth == 1500


@pytest.mark.parametrize(
    ("field_name", "strategy"),
    (
        ("max_object_members", _strategy(parameters={})),
        ("max_list_items", _strategy(parameters={"items": [1, 2, 3]})),
        (
            "max_string_utf8_bytes",
            _strategy(parameters={"text": "x" * 64}),
        ),
        (
            "max_object_key_utf8_bytes",
            _strategy(parameters={"k" * 64: 1}),
        ),
    ),
)
def test_per_container_and_utf8_limits_accept_at_bound_reject_one_under(
    field_name: str,
    strategy: dict[str, object],
) -> None:
    required = {
        "max_object_members": 4,
        "max_list_items": 3,
        "max_string_utf8_bytes": 64,
        "max_object_key_utf8_bytes": 64,
    }[field_name]
    accepted = _accepted_identity(strategy, _limits(**{field_name: required}))
    assert accepted.strategy_hash is not None

    with pytest.raises(SubmissionResourceError) as caught:
        identity_module._validate_and_hash_strategy(
            strategy,
            _limits(**{field_name: required - 1}),
        )
    assert caught.value.code == "submission.resource_limit_exceeded"
    assert str(caught.value) == "Submission resource limit was exceeded."
    assert field_name not in str(caught.value)
    assert str(required) not in str(caught.value)


@pytest.mark.parametrize(
    ("field_name", "strategy", "required_utf8_bytes"),
    (
        (
            "max_string_utf8_bytes",
            _strategy(parameters={"text": "Ω" * 6}),
            12,
        ),
        (
            "max_object_key_utf8_bytes",
            _strategy(parameters={"界" * 5: 1}),
            15,
        ),
    ),
)
def test_multibyte_utf8_limits_count_bytes_not_codepoints(
    field_name: str,
    strategy: dict[str, object],
    required_utf8_bytes: int,
) -> None:
    assert (
        _accepted_identity(
            strategy,
            _limits(**{field_name: required_utf8_bytes}),
        ).strategy_hash
        is not None
    )

    with pytest.raises(SubmissionResourceError) as caught:
        identity_module._validate_and_hash_strategy(
            strategy,
            _limits(**{field_name: required_utf8_bytes - 1}),
        )
    assert caught.value.code == "submission.resource_limit_exceeded"


def test_total_node_limit_accepts_exact_and_rejects_one_under() -> None:
    strategy = _strategy(parameters={"more": [None, True, {"x": 7}]})
    measured = _accepted_identity(strategy)

    exact = _accepted_identity(
        strategy,
        _limits(max_total_value_nodes=measured.value_nodes),
    )
    assert exact.value_nodes == measured.value_nodes
    with pytest.raises(SubmissionResourceError):
        identity_module._validate_and_hash_strategy(
            strategy,
            _limits(max_total_value_nodes=measured.value_nodes - 1),
        )


def test_complete_identity_limit_accepts_exact_and_rejects_one_under() -> None:
    strategy = _strategy(parameters={"large": 2**521 + 17, "text": "fixture"})
    measured = _accepted_identity(strategy)

    exact = _accepted_identity(
        strategy,
        _limits(max_strategy_identity_bytes=measured.identity_bytes),
    )
    assert exact.strategy_hash == measured.strategy_hash
    with pytest.raises(SubmissionResourceError):
        identity_module._validate_and_hash_strategy(
            strategy,
            _limits(max_strategy_identity_bytes=measured.identity_bytes - 1),
        )


def test_dict_key_frames_are_budgeted_before_child_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_enumeration(
        source: dict[object, object], expected: int
    ) -> list[tuple[object, object]]:
        del source, expected
        raise AssertionError("dict children were enumerated after a provable overrun")

    monkeypatch.setattr(identity_module, "_stable_dict_items", forbidden_enumeration)

    with pytest.raises(SubmissionResourceError):
        identity_module._capture_strategy(
            {"a": None, "b": None, "c": None, "d": None},
            _limits(max_strategy_identity_bytes=100),
        )


@pytest.mark.parametrize(
    ("strategy", "target", "identity_limit"),
    (
        ({"kkkk": None}, "kkkk", 65),
        ({"k": "vvvv"}, "vvvv", 66),
    ),
)
def test_utf8_scan_stops_at_remaining_aggregate_identity_budget(
    monkeypatch: pytest.MonkeyPatch,
    strategy: dict[str, object],
    target: str,
    identity_limit: int,
) -> None:
    original_scan = identity_module._utf8_scan
    observed: list[tuple[str, int]] = []

    def scan_spy(value: str, limit: int) -> tuple[int, bool]:
        observed.append((value, limit))
        return original_scan(value, limit)

    def forbidden_semantic_validation(value: object) -> object:
        del value
        raise AssertionError("A2 ran after an aggregate identity overrun")

    monkeypatch.setattr(identity_module, "_utf8_scan", scan_spy)
    monkeypatch.setattr(
        identity_module.strategy_schema,
        "dry_validate",
        forbidden_semantic_validation,
    )

    with pytest.raises(SubmissionResourceError):
        identity_module._validate_and_hash_strategy(
            strategy,
            _limits(
                max_string_utf8_bytes=1000,
                max_object_key_utf8_bytes=1000,
                max_strategy_identity_bytes=identity_limit,
            ),
        )

    assert (target, 3) in observed


def test_huge_integer_is_rejected_before_a2_or_hash_emission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge = 1 << 100_000

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("semantic validation or hash emission ran after overrun")

    monkeypatch.setattr(identity_module.strategy_schema, "dry_validate", forbidden)
    monkeypatch.setattr(identity_module, "_strategy_hash", forbidden)

    with pytest.raises(SubmissionResourceError) as caught:
        identity_module._validate_and_hash_strategy(
            _strategy(parameters={"huge": huge}),
            _limits(max_strategy_identity_bytes=512),
        )
    assert caught.value.code == "submission.resource_limit_exceeded"
    assert str(caught.value) == "Submission resource limit was exceeded."
    assert "100000" not in str(caught.value)


def test_evaluation_binding_matches_independent_tlv_golden() -> None:
    submission_id = SubmissionId("123e4567-e89b-42d3-a456-426614174000")
    strategy_hash = StrategyHash(_independent_strategy_hash(_strategy()))

    binding = identity_module._evaluation_binding(
        submission_id,
        strategy_hash,
        CHALLENGE_KEY,
    )

    assert binding._copy_bytes() == _independent_binding(
        submission_id,
        strategy_hash,
        CHALLENGE_KEY,
    )


@pytest.mark.parametrize("field", ("submission", "hash", "challenge", "version"))
def test_evaluation_binding_changes_for_each_input_field(field: str) -> None:
    submission = SubmissionId("123e4567-e89b-42d3-a456-426614174000")
    strategy_hash = StrategyHash("sha256:" + "d" * 64)
    challenge = CHALLENGE_KEY
    baseline = identity_module._evaluation_binding(submission, strategy_hash, challenge)
    if field == "submission":
        submission = SubmissionId("123e4567-e89b-42d3-a456-426614174001")
    elif field == "hash":
        strategy_hash = StrategyHash("sha256:" + "e" * 64)
    elif field == "challenge":
        challenge = ChallengeKey("a7_other", CHALLENGE_VERSION)
    else:
        challenge = ChallengeKey(CHALLENGE_ID, "fixture-2.0")

    changed = identity_module._evaluation_binding(submission, strategy_hash, challenge)
    assert changed != baseline


def test_evaluation_binding_is_identical_across_distinct_admitting_policies(
    tmp_path: Path,
) -> None:
    generated = uuid.UUID("123e4567-e89b-42d3-a456-426614174000")
    first_service = _service(
        tmp_path / "first",
        limits=_limits(),
        uuid_factory=lambda: generated,
    )
    second_service = _service(
        tmp_path / "second",
        limits=_limits(
            max_total_value_nodes=20_000,
            max_object_members=512,
            max_list_items=512,
            max_string_utf8_bytes=8192,
            max_object_key_utf8_bytes=1024,
            max_strategy_identity_bytes=2_000_000,
            max_challenge_id_bytes=512,
            max_concurrent_identity_builds=16,
            max_retained_submission_records=512,
            max_retained_value_nodes=2_000_000,
            max_retained_strategy_identity_bytes=32_000_000,
        ),
        uuid_factory=lambda: generated,
    )

    first_id = _submit_validate_admit(first_service)
    second_id = _submit_validate_admit(second_service)
    first_pin = _record(first_service, first_id).seed_pin
    second_pin = _record(second_service, second_id).seed_pin

    assert first_id == second_id
    assert first_pin.evaluation_binding == second_pin.evaluation_binding
    assert first_pin.evaluation_binding._copy_bytes() == _independent_binding(
        first_id,
        _record(first_service, first_id).strategy_hash,
        CHALLENGE_KEY,
    )


def test_evaluation_binding_enforces_unsigned_32_payload_representability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submission_id = SubmissionId("123e4567-e89b-42d3-a456-426614174000")
    strategy_hash = StrategyHash("sha256:" + "d" * 64)

    monkeypatch.setattr(identity_module, "_UINT32_MAX", 71)
    assert identity_module._evaluation_binding(
        submission_id,
        strategy_hash,
        CHALLENGE_KEY,
    )

    monkeypatch.setattr(identity_module, "_UINT32_MAX", 70)
    with pytest.raises(ValueError, match="Evaluation binding identity is invalid"):
        identity_module._evaluation_binding(
            submission_id,
            strategy_hash,
            CHALLENGE_KEY,
        )


def test_submit_rejects_u32_unrepresentable_binding_before_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge_id = "a" * 72
    challenge = ChallengeKey(challenge_id, CHALLENGE_VERSION)
    service = _service(
        tmp_path,
        limits=_limits(max_challenge_id_bytes=72),
    )

    def forbidden_hash(strategy: dict[str, object], identity_limit: int) -> object:
        del strategy, identity_limit
        raise AssertionError("hashing ran for an unrepresentable A4 payload")

    monkeypatch.setattr(identity_module, "_UINT32_MAX", 71)
    monkeypatch.setattr(identity_module, "_strategy_hash", forbidden_hash)

    submission_id = service.submit(
        REQUESTER,
        challenge,
        _strategy(challenge_id=challenge_id),
    )

    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.strategy is None
    assert record.strategy_hash is None
    assert service._store.open_index == {}


def test_service_requires_exact_mandatory_configuration(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    policy = _fixture_policy()

    with pytest.raises(SubmissionResourcePolicyError):
        SubmissionService(object(), registry, policy)  # type: ignore[arg-type]
    with pytest.raises(SubmissionRequestError):
        SubmissionService(_limits(), object(), policy)  # type: ignore[arg-type]
    with pytest.raises(SubmissionAdmissionError):
        SubmissionService(_limits(), registry, object())  # type: ignore[arg-type]


def test_submit_creates_received_with_carbon_generated_uuid4(tmp_path: Path) -> None:
    generated = uuid.UUID("123e4567-e89b-42d3-a456-426614174000")
    service = _service(tmp_path, uuid_factory=lambda: generated)

    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    status = service.get_status(submission_id, REQUESTER)

    assert submission_id == SubmissionId(str(generated))
    assert status == SubmissionStatusView(submission_id, SubmissionState.RECEIVED)
    assert submission_id is not _record(service, submission_id).submission_id
    assert status.submission_id is not submission_id
    assert status.submission_id is not _record(service, submission_id).submission_id


@pytest.mark.parametrize(
    "strategy",
    (
        None,
        {},
        _strategy(schema_version="2.0"),
        _strategy(challenge_id="a7_other"),
        _strategy(parameters={"forbidden": {"official_seed": "do-not-retain"}}),
    ),
)
def test_within_budget_invalid_strategy_receives_terminal_rejected_id(
    tmp_path: Path,
    strategy: object,
) -> None:
    service = _service(tmp_path)

    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.REJECTED
    )
    record = _record(service, submission_id)
    assert record.strategy is None
    assert record.strategy_hash is None
    assert submission_id.value not in service._store.open_index.values()
    assert record.attempt_events == []
    assert record.fee_events == []
    with pytest.raises(SubmissionStateError):
        service.mark_validated(submission_id, REQUESTER)


def test_challenge_mismatch_is_rejected_before_strategy_hashing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    def forbidden_hash(strategy: dict[str, object], identity_limit: int) -> object:
        del strategy, identity_limit
        raise AssertionError("Strategy hashing ran before challenge equality")

    monkeypatch.setattr(identity_module, "_strategy_hash", forbidden_hash)

    submission_id = service.submit(
        REQUESTER,
        CHALLENGE_KEY,
        _strategy(challenge_id="different_fixture"),
    )

    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.strategy is None
    assert record.strategy_hash is None
    assert service._store.open_index == {}


def test_resource_overrun_is_pre_id_pre_record_and_non_echoing(tmp_path: Path) -> None:
    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return uuid.uuid4()

    service = _service(
        tmp_path,
        limits=_limits(max_total_value_nodes=1),
        uuid_factory=factory,
    )
    hostile_text = "private-attacker-canary-8db046"

    with pytest.raises(SubmissionResourceError) as caught:
        service.submit(
            REQUESTER,
            CHALLENGE_KEY,
            _strategy(parameters={"value": hostile_text}),
        )

    assert caught.value.code == "submission.resource_limit_exceeded"
    assert hostile_text not in str(caught.value)
    assert calls == 0
    assert service._store.records == {}
    assert service._store.open_index == {}
    assert service._store.retained_value_nodes == 0
    assert service._store.retained_strategy_identity_bytes == 0


def test_challenge_byte_limit_accepts_exact_and_rejects_one_under_pre_id(
    tmp_path: Path,
) -> None:
    exact_service = _service(
        tmp_path / "exact",
        limits=_limits(max_challenge_id_bytes=len(CHALLENGE_ID.encode("ascii"))),
    )
    assert exact_service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return uuid.uuid4()

    under_service = _service(
        tmp_path / "under",
        limits=_limits(max_challenge_id_bytes=len(CHALLENGE_ID.encode("ascii")) - 1),
        uuid_factory=factory,
    )
    with pytest.raises(SubmissionResourceError) as caught:
        under_service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert caught.value.code == "submission.resource_limit_exceeded"
    assert calls == 0
    assert under_service._store.records == {}


def test_challenge_multibyte_scan_counts_utf8_bytes_before_revalidation(
    tmp_path: Path,
) -> None:
    mutated_challenge = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
    object.__setattr__(mutated_challenge, "challenge_id", "Ω" * 4)
    exact = _service(
        tmp_path / "exact",
        limits=_limits(max_challenge_id_bytes=8),
    )
    with pytest.raises(SubmissionRequestError):
        exact.submit(REQUESTER, mutated_challenge, _strategy())

    under = _service(
        tmp_path / "under",
        limits=_limits(max_challenge_id_bytes=7),
    )
    with pytest.raises(SubmissionResourceError) as caught:
        under.submit(REQUESTER, mutated_challenge, _strategy())

    assert caught.value.code == "submission.resource_limit_exceeded"
    assert exact._store.records == {}
    assert under._store.records == {}


def test_identity_build_permit_is_nonblocking_and_pre_identity(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        limits=_limits(max_concurrent_identity_builds=1),
    )
    assert service._store.build_permits.acquire(blocking=False)
    try:
        with pytest.raises(SubmissionResourceError) as caught:
            service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    finally:
        service._store.build_permits.release()

    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert service._store.records == {}


def test_identity_build_permit_is_released_after_failure(tmp_path: Path) -> None:
    service = _service(tmp_path, limits=_limits(max_concurrent_identity_builds=1))

    with pytest.raises(SubmissionResourceError):
        service.submit(
            REQUESTER,
            CHALLENGE_KEY,
            _strategy(parameters={"items": list(range(257))}),
        )
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.RECEIVED
    )


def test_identity_build_permit_is_held_through_guarded_store_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path, limits=_limits(max_concurrent_identity_builds=1))
    original = service_module._validate_and_hash_strategy
    identity_complete = threading.Event()
    finished = threading.Event()
    failures: list[BaseException] = []

    def observed_identity(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)
        identity_complete.set()
        return result

    def submit() -> None:
        try:
            service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            failures.append(error)
        finally:
            finished.set()

    monkeypatch.setattr(
        service_module, "_validate_and_hash_strategy", observed_identity
    )
    service._store.guard.acquire()
    thread = threading.Thread(target=submit)
    try:
        thread.start()
        assert identity_complete.wait(timeout=5.0)
        assert not service._store.build_permits.acquire(blocking=False)
    finally:
        service._store.guard.release()
    assert finished.wait(timeout=5.0)
    thread.join()
    assert failures == []
    assert service._store.build_permits.acquire(blocking=False)
    service._store.build_permits.release()


def test_open_duplicate_precedes_record_capacity_and_creates_nothing(
    tmp_path: Path,
) -> None:
    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return uuid.uuid4()

    service = _service(
        tmp_path,
        limits=_limits(max_retained_submission_records=1),
        uuid_factory=factory,
    )
    first = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    second = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    assert second == first
    assert second is not first
    assert calls == 1
    assert len(service._store.records) == 1
    assert _record(service, first).attempt_events == []
    assert _record(service, first).fee_events == []


def test_terminal_record_frees_open_key_but_not_record_capacity(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        limits=_limits(max_retained_submission_records=1),
    )
    first = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.cancel(first, REQUESTER)

    with pytest.raises(SubmissionResourceError) as caught:
        service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert service.get_status(first, REQUESTER).state is SubmissionState.CANCELLED


@pytest.mark.parametrize(
    "terminal_state",
    (
        SubmissionState.PUBLISHED,
        SubmissionState.REJECTED,
        SubmissionState.FAILED_INFRA,
        SubmissionState.FAILED_STRATEGY,
        SubmissionState.CANCELLED,
    ),
)
def test_every_terminal_state_resubmission_gets_a_fresh_identity(
    tmp_path: Path,
    terminal_state: SubmissionState,
) -> None:
    service = _service(tmp_path / terminal_state.value.lower())
    strategy = None if terminal_state is SubmissionState.REJECTED else _strategy()
    first = service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    if terminal_state is SubmissionState.CANCELLED:
        service.cancel(first, REQUESTER)
    elif terminal_state is not SubmissionState.REJECTED:
        service.mark_validated(first, REQUESTER)
        service.admit_fixture(first, REQUESTER)
        if terminal_state is SubmissionState.FAILED_INFRA:
            service.fail_infrastructure(first, REQUESTER)
        else:
            started = _start(service, first)
            assert started.envelope is not None
            if terminal_state is SubmissionState.FAILED_STRATEGY:
                service.fail_strategy(started.envelope.handle)
            else:
                service.complete_and_publish(started.envelope.handle, _result())

    assert service.get_status(first, REQUESTER).state is terminal_state
    first_record = _record(service, first)
    first_binding = (
        None
        if first_record.strategy_hash is None
        else identity_module._evaluation_binding(
            first,
            first_record.strategy_hash,
            first_record.challenge_key,
        )._copy_bytes()
    )

    second = service.submit(REQUESTER, CHALLENGE_KEY, strategy)
    second_record = _record(service, second)

    assert second != first
    assert len(service._store.records) == 2
    if terminal_state is SubmissionState.REJECTED:
        assert second_record.state is SubmissionState.REJECTED
        assert second_record.strategy_hash is None
        assert service._store.open_index == {}
    else:
        assert second_record.state is SubmissionState.RECEIVED
        assert first.value not in service._store.open_index.values()
        assert second.value in service._store.open_index.values()
        assert first_binding is not None
        assert (
            identity_module._evaluation_binding(
                second,
                second_record.strategy_hash,
                second_record.challenge_key,
            )._copy_bytes()
            != first_binding
        )


def test_uuid_collision_fails_without_regeneration_or_record(tmp_path: Path) -> None:
    candidate = uuid.UUID("123e4567-e89b-42d3-a456-426614174000")
    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return candidate

    service = _service(tmp_path, uuid_factory=factory)
    first = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.cancel(first, REQUESTER)

    with pytest.raises(SubmissionConflictError):
        service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    assert calls == 2
    assert len(service._store.records) == 1
    assert service.get_status(first, REQUESTER).state is SubmissionState.CANCELLED


def test_failed_uuid_candidate_rolls_back_capacity_and_indexes(tmp_path: Path) -> None:
    candidates = iter(
        (
            uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
            uuid.UUID("123e4567-e89b-42d3-a456-426614174000"),
        )
    )
    service = _service(tmp_path, uuid_factory=lambda: next(candidates))

    with pytest.raises(SubmissionConflictError):
        service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert service._store.records == {}
    assert service._store.open_index == {}
    assert service._store.retained_value_nodes == 0

    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert submission_id.value == "123e4567-e89b-42d3-a456-426614174000"


def test_uuid_factory_exception_is_constant_store_failure_without_record(
    tmp_path: Path,
) -> None:
    def fail() -> uuid.UUID:
        raise ValueError("private UUID provider canary 01bfca")

    service = _service(tmp_path, uuid_factory=fail)

    with pytest.raises(SubmissionStoreError) as caught:
        service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert caught.value.code == "submission.store.failure"
    assert str(caught.value) == "Submission store operation failed."
    assert "01bfca" not in str(caught.value)
    assert service._store.records == {}
    assert service._store.open_index == {}


@pytest.mark.parametrize("accepted", (False, True))
def test_submit_return_projection_failure_precedes_record_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    accepted: bool,
) -> None:
    service = _service(tmp_path)
    original_submission_id = service_module.SubmissionId
    calls = 0

    def fail_second_projection(value: str) -> SubmissionId:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected submit return projection failure")
        return original_submission_id(value)

    monkeypatch.setattr(
        service_module,
        "SubmissionId",
        fail_second_projection,
    )
    with pytest.raises(RuntimeError, match="injected submit return projection failure"):
        service.submit(
            REQUESTER,
            CHALLENGE_KEY,
            _strategy() if accepted else None,
        )

    assert calls == 2
    assert service._store.records == {}
    assert service._store.open_index == {}
    assert service._store.retained_value_nodes == 0
    assert service._store.retained_strategy_identity_bytes == 0

    monkeypatch.setattr(service_module, "SubmissionId", original_submission_id)
    assert service.submit(
        REQUESTER,
        CHALLENGE_KEY,
        _strategy() if accepted else None,
    )


@pytest.mark.parametrize(
    ("requester", "challenge"),
    (
        (FeePolicyKey("wrong-nominal"), CHALLENGE_KEY),
        (REQUESTER, object()),
    ),
)
def test_malformed_boundary_wrappers_create_no_id_or_record(
    tmp_path: Path,
    requester: object,
    challenge: object,
) -> None:
    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return uuid.uuid4()

    service = _service(tmp_path, uuid_factory=factory)
    with pytest.raises(SubmissionRequestError):
        service.submit(requester, challenge, _strategy())  # type: ignore[arg-type]
    assert calls == 0
    assert service._store.records == {}


@pytest.mark.parametrize(
    "capacity_field",
    ("max_retained_value_nodes", "max_retained_strategy_identity_bytes"),
)
def test_accepted_retained_capacity_accepts_exact_and_rejects_one_under(
    tmp_path: Path,
    capacity_field: str,
) -> None:
    measured = _accepted_identity()
    required = (
        measured.value_nodes
        if capacity_field == "max_retained_value_nodes"
        else measured.identity_bytes
    )
    exact = _service(
        tmp_path / "exact",
        limits=_limits(**{capacity_field: required}),
    )
    assert exact.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    calls = 0

    def factory() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return uuid.uuid4()

    under = _service(
        tmp_path / "under",
        limits=_limits(**{capacity_field: required - 1}),
        uuid_factory=factory,
    )
    with pytest.raises(SubmissionResourceError) as caught:
        under.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert calls == 0
    assert under._store.records == {}


@pytest.mark.parametrize(
    "capacity_field",
    ("max_retained_value_nodes", "max_retained_strategy_identity_bytes"),
)
def test_retained_strategy_capacities_are_aggregate_across_records(
    tmp_path: Path,
    capacity_field: str,
) -> None:
    strategies = tuple(_strategy(parameters={"value": value}) for value in (1, 2, 3))
    measurements = tuple(_accepted_identity(strategy) for strategy in strategies)
    required = tuple(
        (
            measurement.value_nodes
            if capacity_field == "max_retained_value_nodes"
            else measurement.identity_bytes
        )
        for measurement in measurements
    )
    assert len(set(required)) == 1
    unit = required[0]
    service = _service(
        tmp_path,
        limits=_limits(**{capacity_field: unit * 2}),
    )

    first = service.submit(REQUESTER, CHALLENGE_KEY, strategies[0])
    second = service.submit(REQUESTER, CHALLENGE_KEY, strategies[1])
    with pytest.raises(SubmissionResourceError) as caught:
        service.submit(REQUESTER, CHALLENGE_KEY, strategies[2])

    assert first != second
    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert len(service._store.records) == 2
    observed = (
        service._store.retained_value_nodes
        if capacity_field == "max_retained_value_nodes"
        else service._store.retained_strategy_identity_bytes
    )
    assert observed == unit * 2


@pytest.mark.parametrize(
    "capacity_field",
    ("max_retained_value_nodes", "max_retained_strategy_identity_bytes"),
)
def test_open_duplicate_precedes_each_full_aggregate_retained_capacity(
    tmp_path: Path,
    capacity_field: str,
) -> None:
    strategy = _strategy(parameters={"value": 1})
    measurement = _accepted_identity(strategy)
    required = (
        measurement.value_nodes
        if capacity_field == "max_retained_value_nodes"
        else measurement.identity_bytes
    )
    service = _service(
        tmp_path,
        limits=_limits(**{capacity_field: required}),
    )
    first = service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    duplicate = service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    assert duplicate == first
    assert duplicate is not first
    assert len(service._store.records) == 1
    assert len(service._store.open_index) == 1


@pytest.mark.parametrize(
    "capacity_field",
    ("max_retained_value_nodes", "max_retained_strategy_identity_bytes"),
)
def test_concurrent_last_aggregate_strategy_slot_commits_once(
    tmp_path: Path,
    capacity_field: str,
) -> None:
    strategies = tuple(_strategy(parameters={"value": value}) for value in (1, 2, 3))
    measurements = tuple(_accepted_identity(strategy) for strategy in strategies)
    required = tuple(
        (
            measurement.value_nodes
            if capacity_field == "max_retained_value_nodes"
            else measurement.identity_bytes
        )
        for measurement in measurements
    )
    assert len(set(required)) == 1
    unit = required[0]
    service = _service(
        tmp_path,
        limits=_limits(
            max_concurrent_identity_builds=2,
            **{capacity_field: unit * 2},
        ),
    )
    service.submit(REQUESTER, CHALLENGE_KEY, strategies[0])
    barrier = threading.Barrier(2)
    successes: list[SubmissionId] = []
    failures: list[BaseException] = []

    def worker(strategy: dict[str, object]) -> None:
        try:
            barrier.wait()
            successes.append(service.submit(REQUESTER, CHALLENGE_KEY, strategy))
        except Exception as error:  # noqa: BLE001
            failures.append(error)

    threads = [
        threading.Thread(target=worker, args=(strategy,)) for strategy in strategies[1:]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], SubmissionResourceError)
    assert failures[0].code == "submission.resource_capacity_exceeded"  # type: ignore[attr-defined]
    assert len(service._store.records) == 2
    observed = (
        service._store.retained_value_nodes
        if capacity_field == "max_retained_value_nodes"
        else service._store.retained_strategy_identity_bytes
    )
    assert observed == unit * 2


def test_invalid_flood_is_bounded_by_retained_record_capacity(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        limits=_limits(max_retained_submission_records=2),
    )
    first = service.submit(REQUESTER, CHALLENGE_KEY, None)
    second = service.submit(REQUESTER, CHALLENGE_KEY, None)

    assert first != second
    with pytest.raises(SubmissionResourceError) as caught:
        service.submit(REQUESTER, CHALLENGE_KEY, None)
    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert len(service._store.records) == 2


def test_submit_detaches_and_never_rereads_caller_strategy(tmp_path: Path) -> None:
    strategy = _strategy(parameters={"nested": {"value": 7}, "items": [1, 2]})
    expected_hash = _independent_strategy_hash(strategy)
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    strategy["challenge_id"] = "a7_other"
    strategy["parameters"]["nested"]["value"] = 99  # type: ignore[index]
    strategy["parameters"]["items"].append(3)  # type: ignore[index,union-attr]
    service.mark_validated(submission_id, REQUESTER)
    service.admit_fixture(submission_id, REQUESTER)
    started = _start(service, submission_id)

    assert started.envelope is not None
    assert started.envelope.strategy_hash.value == expected_hash
    assert started.envelope.strategy["challenge_id"] == CHALLENGE_ID
    assert started.envelope.strategy["parameters"] == {
        "nested": {"value": 7},
        "items": [1, 2],
    }


def test_concurrent_exact_open_duplicates_commit_once(tmp_path: Path) -> None:
    calls = 0
    calls_guard = threading.Lock()

    def factory() -> uuid.UUID:
        nonlocal calls
        with calls_guard:
            calls += 1
        return uuid.uuid4()

    worker_count = 16
    service = _service(
        tmp_path,
        limits=_limits(max_concurrent_identity_builds=worker_count),
        uuid_factory=factory,
    )
    barrier = threading.Barrier(worker_count)
    results: list[SubmissionId] = []
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait()
            results.append(service.submit(REQUESTER, CHALLENGE_KEY, _strategy()))
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            failures.append(error)

    threads = [threading.Thread(target=worker) for _ in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert len(results) == worker_count
    assert len({result.value for result in results}) == 1
    assert calls == 1
    assert len(service._store.records) == 1


def test_concurrent_last_record_slot_commits_exactly_once(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        limits=_limits(
            max_concurrent_identity_builds=2,
            max_retained_submission_records=1,
        ),
    )
    barrier = threading.Barrier(2)
    successes: list[SubmissionId] = []
    failures: list[BaseException] = []

    def worker(value: int) -> None:
        try:
            barrier.wait()
            successes.append(
                service.submit(
                    REQUESTER,
                    CHALLENGE_KEY,
                    _strategy(parameters={"value": value}),
                )
            )
        except Exception as error:  # noqa: BLE001
            failures.append(error)

    threads = [threading.Thread(target=worker, args=(value,)) for value in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], SubmissionResourceError)
    assert failures[0].code == "submission.resource_capacity_exceeded"  # type: ignore[attr-defined]
    assert len(service._store.records) == 1


def test_fixture_happy_path_is_exact_and_publishes_only_a6_card(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.RECEIVED
    )

    validated = service.mark_validated(submission_id, REQUESTER)
    assert validated.state is SubmissionState.VALIDATED
    queued = service.admit_fixture(submission_id, REQUESTER)
    assert queued.state is SubmissionState.QUEUED
    assert _record(service, submission_id).fee_events == []

    started = _start(service, submission_id)
    assert started.disposition is StartDisposition.STARTED
    assert started.state is None
    assert type(started.envelope) is FixtureExecutionEnvelope
    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.RUNNING
    assert started.fee_event == FeeEvent(
        sequence=1,
        operation_key=FeeOperationKey("fixture-charge-op-v1"),
        policy_key=FEE_POLICY_KEY,
        kind=FeeEventKind.CHARGE,
        operation_context=FeeOperationContext.INITIAL_RUN_START,
        admission_kind=AdmissionKind.FIXTURE,
        source_attempt_number=1,
        amount_minor=FIXTURE_AMOUNT,
    )

    assert started.envelope is not None
    published = service.complete_and_publish(started.envelope.handle, _result())
    assert published.state is SubmissionState.PUBLISHED
    card = service.read_published(submission_id, REQUESTER)
    assert type(card) is EvaluationCard
    assert card.result_id == submission_id.value
    assert card.status == "SCORED"
    assert card.overall_score == 0.5
    assert card.fixture_origin is True
    assert card.eligible_for_emission is False
    assert not hasattr(card, "strategy")
    assert not hasattr(card, "fee_events")
    assert not hasattr(card, "internal_result")


def test_mandatory_gate_failure_is_completed_science_not_infrastructure(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    published = service.complete_and_publish(
        started.envelope.handle,
        _result(ScoreStatus.MANDATORY_GATE_FAILED),
    )
    card = service.read_published(submission_id, REQUESTER)

    assert published.state is SubmissionState.PUBLISHED
    assert card.status == "MANDATORY_GATE_FAILED"
    assert card.overall_score == 0.0
    assert card.failure_tags == ("mandatory_gate_failed",)
    assert len(_record(service, submission_id).fee_events) == 1


def test_read_published_is_gated_and_requester_bound(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    with pytest.raises(SubmissionStateError):
        service.read_published(submission_id, REQUESTER)
    with pytest.raises(SubmissionAuthorizationError):
        service.read_published(submission_id, OTHER_REQUESTER)


def test_repeated_published_reads_are_fresh_and_fee_free(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.complete_and_publish(started.envelope.handle, _result())
    record = _record(service, submission_id)
    before_attempts = tuple(record.attempt_events)
    before_fees = tuple(record.fee_events)

    first = service.read_published(submission_id, REQUESTER)
    second = service.read_published(submission_id, REQUESTER)
    status = service.get_status(submission_id, REQUESTER)

    assert first == second
    assert first is not second
    assert status.state is SubmissionState.PUBLISHED
    assert tuple(record.attempt_events) == before_attempts
    assert tuple(record.fee_events) == before_fees
    assert [event.kind for event in record.fee_events] == [FeeEventKind.CHARGE]


def test_status_is_minimal_fresh_and_requester_bound(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    first = service.get_status(submission_id, REQUESTER)
    second = service.get_status(submission_id, REQUESTER)

    assert tuple(field.name for field in fields(first)) == ("submission_id", "state")
    assert first == second
    assert first is not second
    assert first.submission_id is not second.submission_id
    for forbidden in (
        "strategy",
        "strategy_hash",
        "requester_identity",
        "attempt_events",
        "fee_events",
        "seed_pin",
        "environment_pin",
        "resource_limits",
        "diagnostics",
    ):
        assert not hasattr(first, forbidden)
    with pytest.raises(SubmissionAuthorizationError):
        service.get_status(submission_id, OTHER_REQUESTER)
    with pytest.raises(SubmissionNotFoundError):
        service.get_status(
            SubmissionId("123e4567-e89b-42d3-a456-426614174000"),
            REQUESTER,
        )


def test_open_duplicate_after_validation_queue_run_and_score_returns_same_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert service.submit(REQUESTER, CHALLENGE_KEY, _strategy()) == submission_id
    service.mark_validated(submission_id, REQUESTER)
    assert service.submit(REQUESTER, CHALLENGE_KEY, _strategy()) == submission_id
    service.admit_fixture(submission_id, REQUESTER)
    assert service.submit(REQUESTER, CHALLENGE_KEY, _strategy()) == submission_id
    started = _start(service, submission_id)
    assert service.submit(REQUESTER, CHALLENGE_KEY, _strategy()) == submission_id

    assert started.envelope is not None

    def expose_scored_then_fail(
        store: CardStore,
        *args: object,
        **kwargs: object,
    ) -> object:
        del store, args, kwargs
        assert _record(service, submission_id).state is SubmissionState.SCORED
        raise CardStoreError()

    monkeypatch.setattr(CardStore, "write_internal", expose_scored_then_fail)
    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(started.envelope.handle, _result())

    assert (
        service.get_status(submission_id, REQUESTER).state
        is SubmissionState.FAILED_INFRA
    )
    fresh = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    assert fresh != submission_id


def test_start_charge_is_atomic_and_replay_has_no_envelope(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)

    first = _start(service, submission_id)
    assert first.disposition is StartDisposition.STARTED
    assert first.envelope is not None
    replay = _start(service, submission_id)

    assert replay.disposition is StartDisposition.ALREADY_STARTED
    assert replay.fee_event == first.fee_event
    assert replay.fee_event is not first.fee_event
    assert replay.envelope is None
    assert replay.state is SubmissionState.RUNNING
    assert len(_record(service, submission_id).fee_events) == 1
    assert _record(service, submission_id).state is SubmissionState.RUNNING


def test_start_result_projection_failure_leaves_queued_and_uncharged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    original_projection = service_module._copy_fee_event

    def fail_projection(value: FeeEvent) -> FeeEvent:
        del value
        raise RuntimeError("injected start result projection failure")

    monkeypatch.setattr(service_module, "_copy_fee_event", fail_projection)
    with pytest.raises(RuntimeError, match="injected start result projection failure"):
        _start(service, submission_id)

    record = _record(service, submission_id)
    assert record.state is SubmissionState.QUEUED
    assert record.current_handle is None
    assert record.terminal_infra_operation_key is None
    assert [event.kind for event in record.attempt_events] == [AttemptEventKind.QUEUED]
    assert record.fee_events == []

    monkeypatch.setattr(service_module, "_copy_fee_event", original_projection)
    started = _start(service, submission_id)
    assert started.disposition is StartDisposition.STARTED
    assert started.envelope is not None
    assert record.state is SubmissionState.RUNNING
    assert len(record.fee_events) == 1


def test_start_refund_key_construction_failure_precedes_every_record_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    charge_key = FeeOperationKey("precommit-charge")
    refund_key = FeeOperationKey("precommit-refund")
    original_post_init = FeeOperationKey.__post_init__
    calls = 0

    def fail_reserved_key(value: FeeOperationKey) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("injected reserved refund key failure")
        original_post_init(value)

    monkeypatch.setattr(FeeOperationKey, "__post_init__", fail_reserved_key)
    with pytest.raises(RuntimeError, match="injected reserved refund key failure"):
        service.start_fixture_attempt(
            submission_id,
            REQUESTER,
            charge_key,
            refund_key,
        )

    record = _record(service, submission_id)
    assert calls == 3
    assert record.state is SubmissionState.QUEUED
    assert record.current_handle is None
    assert record.terminal_infra_operation_key is None
    assert [event.kind for event in record.attempt_events] == [AttemptEventKind.QUEUED]
    assert record.fee_events == []

    monkeypatch.setattr(FeeOperationKey, "__post_init__", original_post_init)
    started = service.start_fixture_attempt(
        submission_id,
        REQUESTER,
        charge_key,
        refund_key,
    )
    assert started.disposition is StartDisposition.STARTED


def test_start_replay_precedes_terminal_state_check(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    first = _start(service, submission_id)
    assert first.envelope is not None
    service.fail_strategy(first.envelope.handle)

    replay = _start(service, submission_id)

    assert replay.disposition is StartDisposition.ALREADY_STARTED
    assert replay.state is SubmissionState.FAILED_STRATEGY
    assert replay.envelope is None
    assert replay.fee_event == first.fee_event


@pytest.mark.parametrize(
    "operation_name",
    ("validate", "admit", "retry", "fail_strategy", "publish", "cancel"),
)
def test_status_projection_failure_precedes_every_lifecycle_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation_name: str,
) -> None:
    service = _service(tmp_path)
    if operation_name == "validate":
        submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
        operation: Callable[[], object] = lambda: service.mark_validated(
            submission_id, REQUESTER
        )
        expected_state = SubmissionState.VALIDATED
    elif operation_name == "admit":
        submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
        service.mark_validated(submission_id, REQUESTER)
        operation = lambda: service.admit_fixture(submission_id, REQUESTER)
        expected_state = SubmissionState.QUEUED
    else:
        submission_id = _submit_validate_admit(service)
        if operation_name == "cancel":
            operation = lambda: service.cancel(submission_id, REQUESTER)
            expected_state = SubmissionState.CANCELLED
        else:
            started = _start(service, submission_id)
            assert started.envelope is not None
            handle = started.envelope.handle
            if operation_name == "retry":
                operation = lambda: service.retry_infrastructure(handle)
                expected_state = SubmissionState.QUEUED
            elif operation_name == "fail_strategy":
                operation = lambda: service.fail_strategy(handle)
                expected_state = SubmissionState.FAILED_STRATEGY
            else:
                operation = lambda: service.complete_and_publish(handle, _result())
                expected_state = SubmissionState.PUBLISHED

    before = _lifecycle_snapshot(service, submission_id)
    original_status = service_module._status

    def fail_status(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("injected status projection failure")

    monkeypatch.setattr(service_module, "_status", fail_status)
    with pytest.raises(RuntimeError, match="injected status projection failure"):
        operation()
    assert _lifecycle_snapshot(service, submission_id) == before

    monkeypatch.setattr(service_module, "_status", original_status)
    result = operation()
    assert type(result) is SubmissionStatusView
    assert result.state is expected_state


@pytest.mark.parametrize(
    "operation_name",
    ("retry_terminal", "fail_handle", "fail_retry_queue"),
)
def test_refund_projection_failure_precedes_terminal_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation_name: str,
) -> None:
    policy = _fixture_policy(
        max_attempts=1 if operation_name == "retry_terminal" else 2
    )
    service = _service(tmp_path, policy=policy)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    handle = started.envelope.handle
    if operation_name == "retry_terminal":
        operation: Callable[[], object] = lambda: service.retry_infrastructure(handle)
    elif operation_name == "fail_handle":
        operation = lambda: service.fail_infrastructure(handle)
    else:
        retried = service.retry_infrastructure(handle)
        assert type(retried) is SubmissionStatusView
        assert retried.state is SubmissionState.QUEUED
        operation = lambda: service.fail_infrastructure(submission_id, REQUESTER)

    before = _lifecycle_snapshot(service, submission_id)
    original_projection = service_module._copy_fee_event

    def fail_projection(value: FeeEvent) -> FeeEvent:
        del value
        raise RuntimeError("injected refund projection failure")

    monkeypatch.setattr(service_module, "_copy_fee_event", fail_projection)
    with pytest.raises(RuntimeError, match="injected refund projection failure"):
        operation()
    assert _lifecycle_snapshot(service, submission_id) == before

    monkeypatch.setattr(service_module, "_copy_fee_event", original_projection)
    refund = operation()
    assert type(refund) is FeeEvent
    assert refund.kind is FeeEventKind.REFUND
    assert _record(service, submission_id).state is SubmissionState.FAILED_INFRA


@pytest.mark.parametrize(
    ("charge", "refund"),
    (
        ("same-operation", "same-operation"),
        ("fixture-charge-op-v1", "changed-refund-op"),
    ),
)
def test_start_operation_key_conflicts_are_atomic(
    tmp_path: Path,
    charge: str,
    refund: str,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    if charge == "fixture-charge-op-v1":
        _start(service, submission_id)

    with pytest.raises(SubmissionConflictError):
        _start(service, submission_id, charge=charge, refund=refund)

    record = _record(service, submission_id)
    if charge == "same-operation":
        assert record.state is SubmissionState.QUEUED
        assert record.fee_events == []
        assert record.current_handle is None
    else:
        assert record.state is SubmissionState.RUNNING
        assert len(record.fee_events) == 1


def test_fresh_start_keys_reach_source_state_after_used_key_resolution(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    _start(service, submission_id)

    with pytest.raises(SubmissionStateError):
        _start(
            service,
            submission_id,
            charge="fresh-charge-operation",
            refund="fresh-refund-operation",
        )
    with pytest.raises(SubmissionConflictError):
        _start(
            service,
            submission_id,
            charge="fresh-charge-operation",
            refund="fixture-refund-op-v1",
        )


def test_zero_amount_charge_and_terminal_refund_remain_exact_integer_events(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, policy=_fixture_policy(amount_minor=0, max_attempts=1))
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    refund = service.fail_infrastructure(started.envelope.handle)

    assert type(refund) is FeeEvent
    assert started.fee_event.amount_minor == 0
    assert refund.amount_minor == 0
    assert refund.sequence == 2
    assert refund.charge_operation_key == started.fee_event.operation_key


def test_prestart_infrastructure_failure_has_no_charge_or_refund(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)

    result = service.fail_infrastructure(submission_id, REQUESTER)

    assert result is None
    assert (
        service.get_status(submission_id, REQUESTER).state
        is SubmissionState.FAILED_INFRA
    )
    record = _record(service, submission_id)
    assert record.fee_events == []
    assert [(event.attempt_number, event.kind) for event in record.attempt_events] == [
        (1, AttemptEventKind.QUEUED),
        (1, AttemptEventKind.FAILED_INFRA),
    ]


def test_running_infrastructure_failure_refunds_full_balance_and_replays(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    refund = service.fail_infrastructure(started.envelope.handle)
    replay = service.fail_infrastructure(started.envelope.handle)

    assert type(refund) is FeeEvent
    assert replay == refund
    assert replay is not refund
    assert refund.sequence == 2
    assert refund.kind is FeeEventKind.REFUND
    assert refund.operation_context is FeeOperationContext.TERMINAL_INFRA
    assert refund.source_attempt_number == 1
    assert refund.amount_minor == FIXTURE_AMOUNT
    assert refund.charge_operation_key == started.fee_event.operation_key
    assert (
        service.get_status(submission_id, REQUESTER).state
        is SubmissionState.FAILED_INFRA
    )
    assert len(_record(service, submission_id).fee_events) == 2


def test_wrong_historical_handle_conflicts_with_refund_replay(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    handle = started.envelope.handle
    service.fail_infrastructure(handle)
    wrong = ExecutionAttemptHandle(
        submission_id=handle.submission_id,
        attempt_number=2,
        admission_kind=handle.admission_kind,
        seed_pin=handle.seed_pin,
        environment_pin=handle.environment_pin,
    )

    with pytest.raises(SubmissionConflictError):
        service.fail_infrastructure(wrong)
    assert len(_record(service, submission_id).fee_events) == 2


def test_hostile_nested_handle_field_is_non_echoing_and_cannot_mutate(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    handle = started.envelope.handle
    before = list(_record(service, submission_id).attempt_events)
    object.__setattr__(handle, "seed_pin", _HostileHandleField())

    with pytest.raises(SubmissionRequestError) as caught:
        service.fail_strategy(handle)

    assert caught.value.code == "submission.request.invalid"
    assert "hostile-handle" not in str(caught.value)
    record = _record(service, submission_id)
    assert record.state is SubmissionState.RUNNING
    assert record.attempt_events == before
    assert len(record.fee_events) == 1


def test_retry_preserves_identity_and_pins_and_never_recharges(tmp_path: Path) -> None:
    service = _service(tmp_path, policy=_fixture_policy(max_attempts=2))
    submission_id = _submit_validate_admit(service)
    first = _start(service, submission_id)
    assert first.envelope is not None
    first_envelope = first.envelope

    queued = service.retry_infrastructure(first_envelope.handle)
    assert type(queued) is SubmissionStatusView
    assert queued.state is SubmissionState.QUEUED
    second_envelope = service.start_fixture_retry_attempt(submission_id, REQUESTER)

    assert second_envelope.handle.attempt_number == 2
    assert second_envelope.handle.submission_id == first_envelope.handle.submission_id
    assert second_envelope.handle.seed_pin == first_envelope.handle.seed_pin
    assert (
        second_envelope.handle.environment_pin == first_envelope.handle.environment_pin
    )
    assert second_envelope.strategy_hash == first_envelope.strategy_hash
    assert second_envelope.challenge_key == first_envelope.challenge_key
    assert second_envelope.strategy == first_envelope.strategy
    assert second_envelope.strategy is not first_envelope.strategy
    assert len(_record(service, submission_id).fee_events) == 1

    refund = service.retry_infrastructure(second_envelope.handle)
    assert type(refund) is FeeEvent
    assert refund.kind is FeeEventKind.REFUND
    assert refund.source_attempt_number == 2
    assert refund.amount_minor == FIXTURE_AMOUNT
    assert len(_record(service, submission_id).fee_events) == 2


def test_charged_retry_queue_terminal_infra_refunds_without_current_handle(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.retry_infrastructure(started.envelope.handle)

    refund = service.fail_infrastructure(submission_id, REQUESTER)
    replay = service.fail_infrastructure(submission_id, REQUESTER)

    assert type(refund) is FeeEvent
    assert replay == refund
    assert refund.kind is FeeEventKind.REFUND
    assert refund.operation_context is FeeOperationContext.TERMINAL_INFRA
    assert refund.source_attempt_number == 2
    assert refund.amount_minor == FIXTURE_AMOUNT
    assert (
        service.get_status(submission_id, REQUESTER).state
        is SubmissionState.FAILED_INFRA
    )


def test_stale_handle_cannot_mutate_retry_attempt(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    first = _start(service, submission_id)
    assert first.envelope is not None
    first_handle = first.envelope.handle
    service.retry_infrastructure(first_handle)
    second = service.start_fixture_retry_attempt(submission_id, REQUESTER)

    for operation in (
        service.retry_infrastructure,
        service.fail_strategy,
        service.fail_infrastructure,
        lambda handle: service.complete_and_publish(handle, _result()),
    ):
        with pytest.raises(SubmissionStateError):
            operation(first_handle)
    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.RUNNING
    assert _record(service, submission_id).current_handle == second.handle
    assert len(_record(service, submission_id).fee_events) == 1


def test_fail_strategy_is_terminal_science_execution_class_without_refund(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    failed = service.fail_strategy(started.envelope.handle)

    assert failed.state is SubmissionState.FAILED_STRATEGY
    record = _record(service, submission_id)
    assert len(record.fee_events) == 1
    assert record.attempt_events[-1] == AttemptEvent(
        1,
        AttemptEventKind.FAILED_STRATEGY,
    )
    with pytest.raises(SubmissionStateError):
        service.retry_infrastructure(started.envelope.handle)


@pytest.mark.parametrize(
    "source_state",
    (SubmissionState.RECEIVED, SubmissionState.VALIDATED, SubmissionState.QUEUED),
)
def test_requester_can_cancel_only_each_ratified_source_without_fee(
    tmp_path: Path,
    source_state: SubmissionState,
) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    if source_state in (SubmissionState.VALIDATED, SubmissionState.QUEUED):
        service.mark_validated(submission_id, REQUESTER)
    if source_state is SubmissionState.QUEUED:
        service.admit_fixture(submission_id, REQUESTER)

    cancelled = service.cancel(submission_id, REQUESTER)

    assert cancelled.state is SubmissionState.CANCELLED
    record = _record(service, submission_id)
    assert record.fee_events == []
    expected_attempts = (
        []
        if source_state is not SubmissionState.QUEUED
        else [
            AttemptEvent(1, AttemptEventKind.QUEUED),
            AttemptEvent(1, AttemptEventKind.CANCELLED),
        ]
    )
    assert record.attempt_events == expected_attempts
    with pytest.raises(SubmissionStateError):
        service.cancel(submission_id, REQUESTER)


def test_cancellation_is_requester_bound_and_denied_while_running(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)

    with pytest.raises(SubmissionAuthorizationError):
        service.cancel(submission_id, OTHER_REQUESTER)
    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.QUEUED

    started = _start(service, submission_id)
    with pytest.raises(SubmissionStateError):
        service.cancel(submission_id, REQUESTER)
    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.RUNNING
    assert len(_record(service, submission_id).fee_events) == 1
    assert started.envelope is not None


def test_retry_queued_cancellation_retains_prior_charge_without_adjustment(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.retry_infrastructure(started.envelope.handle)

    cancelled = service.cancel(submission_id, REQUESTER)

    assert cancelled.state is SubmissionState.CANCELLED
    record = _record(service, submission_id)
    assert len(record.fee_events) == 1
    assert record.fee_events[0].kind is FeeEventKind.CHARGE
    assert record.attempt_events[-1] == AttemptEvent(2, AttemptEventKind.CANCELLED)


def test_fixture_ineligibility_rejects_before_attempt_or_fee(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    registry.save(
        replace(registry.load(CHALLENGE_ID, CHALLENGE_VERSION), status="draft")
    )
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionAdmissionError) as caught:
        service.admit_fixture(submission_id, REQUESTER)

    assert caught.value.code == "admission.challenge_not_fixture_eligible"
    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.attempt_events == []
    assert record.fee_events == []
    assert submission_id.value not in service._store.open_index.values()


def test_a3_caught_artifact_failure_is_generic_fixture_denial(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    record = registry.load(CHALLENGE_ID, CHALLENGE_VERSION)
    binding = record.artifacts["fixture_bundle"]
    assert binding.path is not None
    registry.artifact_root.joinpath(*binding.path.split("/")).unlink()
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionAdmissionError) as caught:
        service.admit_fixture(submission_id, REQUESTER)

    assert caught.value.code == "admission.challenge_not_fixture_eligible"
    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.REJECTED
    )
    assert _record(service, submission_id).attempt_events == []
    assert _record(service, submission_id).fee_events == []


def test_backbone_denial_rejects_before_attempt_or_fee(tmp_path: Path) -> None:
    registry = _fixture_registry(tmp_path)
    registry.save(
        replace(
            registry.load(CHALLENGE_ID, CHALLENGE_VERSION),
            allowed_backbones=("uno",),
        )
    )
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionAdmissionError) as caught:
        service.admit_fixture(submission_id, REQUESTER)

    assert caught.value.code == "admission.backbone_not_allowed"
    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.attempt_events == []
    assert record.fee_events == []


@pytest.mark.parametrize("operation", ("eligibility", "backbone"))
def test_escaping_a3_failure_is_non_echoing_and_leaves_validated_uncharged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    registry = _fixture_registry(tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RegistryError("fixture.test_failure", "", "safe fixture failure")

    if operation == "eligibility":
        monkeypatch.setattr(registry, "assess_live_eligibility", fail)
    else:
        monkeypatch.setattr(registry, "is_backbone_allowed", fail)
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionIntegrationError) as caught:
        service.admit_fixture(submission_id, REQUESTER)
    assert caught.value.code == "submission.integration.failure"
    assert str(caught.value) == "Submission integration failed."
    assert "fixture.test_failure" not in str(caught.value)

    record = _record(service, submission_id)
    assert record.state is SubmissionState.VALIDATED
    assert record.attempt_events == []
    assert record.fee_events == []
    assert record.admission_kind is None


def test_positive_production_gate_still_fails_closed_without_later_seams(
    tmp_path: Path,
) -> None:
    registry = _production_registry(tmp_path)
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionIntegrationError):
        service.admit_production(submission_id, REQUESTER)

    record = _record(service, submission_id)
    assert record.state is SubmissionState.VALIDATED
    assert record.admission_kind is None
    assert record.attempt_number is None
    assert record.attempt_events == []
    assert record.fee_events == []


def test_production_backbone_denial_rejects_before_missing_seam(tmp_path: Path) -> None:
    registry = _production_registry(tmp_path, allowed_backbones=("uno",))
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionAdmissionError) as caught:
        service.admit_production(submission_id, REQUESTER)

    assert caught.value.code == "admission.backbone_not_allowed"
    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.attempt_events == []
    assert record.fee_events == []


@pytest.mark.parametrize("operation", ("live", "backbone"))
def test_escaping_production_a3_exception_is_non_echoing_and_leaves_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    registry = _production_registry(tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("injected escaping A3 exception")

    target = "is_effectively_live" if operation == "live" else "is_backbone_allowed"
    monkeypatch.setattr(registry, target, fail)
    service = _service(tmp_path / "service", registry=registry)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionIntegrationError) as caught:
        service.admit_production(submission_id, REQUESTER)
    assert caught.value.code == "submission.integration.failure"
    assert str(caught.value) == "Submission integration failed."
    assert "injected escaping" not in str(caught.value)

    record = _record(service, submission_id)
    assert record.state is SubmissionState.VALIDATED
    assert record.admission_kind is None
    assert record.attempt_events == []
    assert record.fee_events == []


def test_fixture_never_falls_back_to_production_or_crosses_start_kind(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)

    with pytest.raises(SubmissionAdmissionError) as caught:
        service.admit_production(submission_id, REQUESTER)
    assert caught.value.code == "admission.challenge_not_live"
    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.REJECTED
    )

    second = _submit_validate_admit(service)
    with pytest.raises(SubmissionIntegrationError):
        service.start_production_attempt(
            second,
            REQUESTER,
            FeeOperationKey("production-charge-blocked"),
            FeeOperationKey("production-refund-blocked"),
        )
    assert service.get_status(second, REQUESTER).state is SubmissionState.QUEUED
    assert _record(service, second).fee_events == []


def test_queue_admission_is_atomic_no_fee_and_pins_exact_binding(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
    service.mark_validated(submission_id, REQUESTER)
    service.admit_fixture(submission_id, REQUESTER)
    record = _record(service, submission_id)

    assert record.state is SubmissionState.QUEUED
    assert record.admission_kind is AdmissionKind.FIXTURE
    assert record.terminal_infra_disposition is FeeEventKind.REFUND
    assert record.attempt_number == 1
    assert record.attempt_events == [AttemptEvent(1, AttemptEventKind.QUEUED)]
    assert record.fee_events == []
    assert record.seed_pin.challenge_key == CHALLENGE_KEY
    assert record.seed_pin.generator_version == GENERATOR_VERSION
    assert record.seed_pin.generator_digest == GENERATOR_DIGEST
    assert record.seed_pin.scoring_version == SCORING_VERSION
    assert record.seed_pin.scoring_digest == SCORING_DIGEST
    assert record.seed_pin.evaluation_binding._copy_bytes() == _independent_binding(
        submission_id,
        record.strategy_hash,
        CHALLENGE_KEY,
    )
    assert record.environment_pin == _environment_pin()


@pytest.mark.parametrize(
    "status",
    (ScoreStatus.PACK_NOT_READY,),
)
def test_noncompletion_a5_status_is_operational_retry_then_terminal_refund(
    tmp_path: Path,
    status: ScoreStatus,
) -> None:
    service = _service(tmp_path, policy=_fixture_policy(max_attempts=2))
    submission_id = _submit_validate_admit(service)
    first = _start(service, submission_id)
    assert first.envelope is not None

    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(first.envelope.handle, _result(status))
    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.QUEUED
    assert len(_record(service, submission_id).fee_events) == 1

    second = service.start_fixture_retry_attempt(submission_id, REQUESTER)
    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(second.handle, _result(status))

    record = _record(service, submission_id)
    assert record.state is SubmissionState.FAILED_INFRA
    assert [event.kind for event in record.fee_events] == [
        FeeEventKind.CHARGE,
        FeeEventKind.REFUND,
    ]
    assert record.fee_events[-1].operation_context is FeeOperationContext.TERMINAL_INFRA
    assert all(
        event.kind is not AttemptEventKind.SCORED for event in record.attempt_events
    )


@pytest.mark.parametrize(
    "pin",
    (
        _score_pack_pin(challenge_key=ChallengeKey("a7_other", CHALLENGE_VERSION)),
        _score_pack_pin(scoring_version="fixture-scoring-v2.0"),
        _score_pack_pin(scoring_digest="sha256:" + "d" * 64),
        _score_pack_pin(generator_version="fixture-generator-v2.0"),
        _score_pack_pin(generator_digest="sha256:" + "e" * 64),
    ),
)
def test_each_a5_a4_pin_mismatch_is_infrastructure_not_science(
    tmp_path: Path,
    pin: ScorePackPin,
) -> None:
    service = _service(tmp_path, policy=_fixture_policy(max_attempts=1))
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(started.envelope.handle, _result(pin=pin))

    record = _record(service, submission_id)
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.attempt_events[-1].kind is AttemptEventKind.FAILED_INFRA
    assert all(
        event.kind is not AttemptEventKind.SCORED for event in record.attempt_events
    )
    assert record.fee_events[-1].kind is FeeEventKind.REFUND
    with pytest.raises(SubmissionStateError):
        service.read_published(submission_id, REQUESTER)


class _InternalResultSubclass(InternalResult):
    __slots__ = ()


def test_result_subclass_is_operational_integration_failure(tmp_path: Path) -> None:
    source = _result()
    subclassed = _InternalResultSubclass(
        status=source.status,
        pack_pin=source.pack_pin,
        gate_decisions=source.gate_decisions,
        leg_scores=source.leg_scores,
        combined_score=source.combined_score,
        eligible_for_emission=source.eligible_for_emission,
    )
    service = _service(tmp_path, policy=_fixture_policy(max_attempts=1))
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(started.envelope.handle, subclassed)
    assert (
        service.get_status(submission_id, REQUESTER).state
        is SubmissionState.FAILED_INFRA
    )


@pytest.mark.parametrize("failure", (CardConflictError, CardStoreError))
def test_a6_write_failure_becomes_publication_infra_refund_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[Exception],
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        assert _record(service, submission_id).state is SubmissionState.SCORED
        raise failure()

    monkeypatch.setattr(CardStore, "write_internal", fail)
    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(started.envelope.handle, _result())

    record = _record(service, submission_id)
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.current_handle is None
    assert record.attempt_events[-2:] == [
        AttemptEvent(1, AttemptEventKind.SCORED),
        AttemptEvent(1, AttemptEventKind.FAILED_INFRA),
    ]
    assert record.fee_events[-1].kind is FeeEventKind.REFUND
    assert (
        record.fee_events[-1].operation_context is FeeOperationContext.PUBLICATION_INFRA
    )
    with pytest.raises(SubmissionConflictError):
        service.fail_infrastructure(started.envelope.handle)
    assert len(record.fee_events) == 2


def test_publication_failure_uses_precomputed_open_index_commit_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    store_type = type(service._store)
    original = store_type._open_key_for_record_locked
    calls = 0

    def fail_if_recomputed(record: object) -> tuple[str, str, str, str]:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("open key was recomputed after lifecycle mutation")
        return original(record)  # type: ignore[arg-type]

    def fail_write(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise CardStoreError()

    monkeypatch.setattr(
        store_type,
        "_open_key_for_record_locked",
        staticmethod(fail_if_recomputed),
    )
    monkeypatch.setattr(CardStore, "write_internal", fail_write)

    with pytest.raises(SubmissionIntegrationError):
        service.complete_and_publish(started.envelope.handle, _result())

    record = _record(service, submission_id)
    assert calls == 1
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.fee_events[-1].kind is FeeEventKind.REFUND
    assert submission_id.value not in service._store.open_index.values()


def test_a6_already_present_exact_write_permits_publication(tmp_path: Path) -> None:
    generated = uuid.UUID("123e4567-e89b-42d3-a456-426614174000")
    seeded_result = _result()
    seed = (
        CardRecordKey(str(generated)),
        RequesterAuthorizationKey(REQUESTER.value),
        seeded_result,
    )
    service = _service(
        tmp_path,
        uuid_factory=lambda: generated,
        card_store_seed=seed,
    )
    object.__setattr__(seeded_result, "combined_score", 0.75)
    del seed
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    published = service.complete_and_publish(started.envelope.handle, _result())

    assert published.state is SubmissionState.PUBLISHED
    assert service.read_published(submission_id, REQUESTER).status == "SCORED"
    assert len(_record(service, submission_id).fee_events) == 1


@pytest.mark.parametrize("invalid", (object(), "INSERTED", "ALREADY_PRESENT"))
def test_unrecognized_a6_disposition_fails_closed_with_publication_refund(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid: object,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    def invalid_disposition(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return invalid

    monkeypatch.setattr(CardStore, "write_internal", invalid_disposition)
    with pytest.raises((SubmissionIntegrationError, SubmissionStoreError)):
        service.complete_and_publish(started.envelope.handle, _result())

    record = _record(service, submission_id)
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.fee_events[-1].kind is FeeEventKind.REFUND
    assert (
        record.fee_events[-1].operation_context is FeeOperationContext.PUBLICATION_INFRA
    )


def test_repeated_completion_after_publication_is_typed_no_mutation(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.complete_and_publish(started.envelope.handle, _result())
    before = (
        list(_record(service, submission_id).attempt_events),
        list(_record(service, submission_id).fee_events),
    )

    with pytest.raises(SubmissionStateError):
        service.complete_and_publish(started.envelope.handle, _result())

    assert (
        service.get_status(submission_id, REQUESTER).state is SubmissionState.PUBLISHED
    )
    assert _record(service, submission_id).attempt_events == before[0]
    assert _record(service, submission_id).fee_events == before[1]


def test_build_permit_precedes_challenge_scan_for_mutated_exact_wrapper(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        limits=_limits(
            max_concurrent_identity_builds=1,
            max_challenge_id_bytes=16,
        ),
    )
    challenge = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
    object.__setattr__(challenge, "challenge_id", "x" * 10_000)
    assert service._store.build_permits.acquire(blocking=False)
    try:
        with pytest.raises(SubmissionResourceError) as caught:
            service.submit(REQUESTER, challenge, _strategy())
    finally:
        service._store.build_permits.release()

    assert caught.value.code == "submission.resource_capacity_exceeded"
    assert service._store.records == {}


def test_observed_capture_instability_is_permanent_safe_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def unstable(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise identity_module._CaptureUnstable()

    monkeypatch.setattr(identity_module, "_stable_dict_items", unstable)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    record = _record(service, submission_id)
    assert record.state is SubmissionState.REJECTED
    assert record.strategy is None
    assert record.strategy_hash is None
    assert submission_id.value not in service._store.open_index.values()


class _FailingOpenIndex(dict[object, object]):
    def __setitem__(self, key: object, value: object) -> None:
        super().__setitem__(key, value)
        raise RuntimeError("injected open-index commit failure")


class _FailingRecordMap(dict[object, object]):
    def __setitem__(self, key: object, value: object) -> None:
        super().__setitem__(key, value)
        raise RuntimeError("injected record commit failure")


def test_accepted_insert_failure_rolls_back_records_indexes_and_counters(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service._store.open_index = _FailingOpenIndex()

    with pytest.raises(RuntimeError, match="injected open-index commit failure"):
        service.submit(REQUESTER, CHALLENGE_KEY, _strategy())

    assert service._store.records == {}
    assert service._store.open_index == {}
    assert service._store.retained_value_nodes == 0
    assert service._store.retained_strategy_identity_bytes == 0
    service._store.open_index = {}
    assert service.submit(REQUESTER, CHALLENGE_KEY, _strategy())


@pytest.mark.parametrize("accepted", (True, False))
def test_record_insert_after_write_failure_rolls_back_every_commit_surface(
    tmp_path: Path,
    accepted: bool,
) -> None:
    service = _service(tmp_path)
    service._store.records = _FailingRecordMap()
    strategy = _strategy() if accepted else None

    with pytest.raises(RuntimeError, match="injected record commit failure"):
        service.submit(REQUESTER, CHALLENGE_KEY, strategy)

    assert service._store.records == {}
    assert service._store.open_index == {}
    assert service._store.retained_value_nodes == 0
    assert service._store.retained_strategy_identity_bytes == 0


def test_submit_reads_each_caller_identity_field_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    requester = RequesterIdentity("single-read-requester")
    challenge = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
    requester_value = _ObservedSlot(RequesterIdentity.value, requester)
    challenge_id = _ObservedSlot(ChallengeKey.challenge_id, challenge)
    challenge_version = _ObservedSlot(ChallengeKey.version, challenge)
    monkeypatch.setattr(RequesterIdentity, "value", requester_value)
    monkeypatch.setattr(ChallengeKey, "challenge_id", challenge_id)
    monkeypatch.setattr(ChallengeKey, "version", challenge_version)

    submission_id = service.submit(requester, challenge, _strategy())

    assert requester_value.reads == 1
    assert challenge_id.reads == 1
    assert challenge_version.reads == 1
    record = _record(service, submission_id)
    assert record.requester_identity.value == "single-read-requester"
    assert record.challenge_key.challenge_id == CHALLENGE_ID
    assert record.challenge_key.version == CHALLENGE_VERSION


def test_submit_owns_request_primitives_before_strategy_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    requester = RequesterIdentity("barrier-requester")
    challenge = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
    identity_entered = threading.Event()
    release_identity = threading.Event()
    original_identity = service_module._validate_and_hash_strategy
    submission_ids: list[SubmissionId] = []
    failures: list[BaseException] = []

    def paused_identity(*args: object, **kwargs: object) -> object:
        identity_entered.set()
        if not release_identity.wait(timeout=5.0):  # pragma: no cover
            raise AssertionError("test did not release Strategy processing")
        return original_identity(*args, **kwargs)

    def submit() -> None:
        try:
            submission_ids.append(service.submit(requester, challenge, _strategy()))
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            failures.append(error)

    monkeypatch.setattr(
        service_module,
        "_validate_and_hash_strategy",
        paused_identity,
    )
    thread = threading.Thread(target=submit)
    thread.start()
    try:
        assert identity_entered.wait(timeout=5.0)
        object.__setattr__(requester, "value", "mutated-barrier-requester")
        object.__setattr__(challenge, "challenge_id", "a7_mutated")
        object.__setattr__(challenge, "version", "fixture-9.0")
    finally:
        release_identity.set()
    thread.join()

    assert failures == []
    assert len(submission_ids) == 1
    submission_id = submission_ids[0]
    owned_requester = RequesterIdentity("barrier-requester")
    service.mark_validated(submission_id, owned_requester)
    service.admit_fixture(submission_id, owned_requester)
    record = _record(service, submission_id)
    assert record.requester_identity == owned_requester
    assert record.challenge_key == CHALLENGE_KEY
    assert record.seed_pin.challenge_key == CHALLENGE_KEY
    assert record.seed_pin.evaluation_binding._copy_bytes() == _independent_binding(
        submission_id,
        record.strategy_hash,
        CHALLENGE_KEY,
    )
    assert any(
        key[:3] == ("barrier-requester", CHALLENGE_ID, CHALLENGE_VERSION)
        and value == submission_id.value
        for key, value in service._store.open_index.items()
    )


def test_policy_and_returned_values_are_owned_against_low_level_mutation(
    tmp_path: Path,
) -> None:
    limits = _limits()
    policy = _fixture_policy()
    requester = RequesterIdentity("owned-input-requester")
    challenge = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
    service = _service(tmp_path, limits=limits, policy=policy)
    object.__setattr__(limits, "max_total_value_nodes", 1)
    object.__setattr__(policy, "amount_minor", 999_999)
    object.__setattr__(policy, "max_attempts", 99)
    object.__setattr__(policy, "generator_version", "mutated-generator")
    object.__setattr__(policy, "generator_digest", "sha256:" + "f" * 64)
    object.__setattr__(policy, "scoring_version", "mutated-scoring")
    object.__setattr__(policy, "scoring_digest", "sha256:" + "f" * 64)
    object.__setattr__(policy.fee_policy_key, "value", "mutated-policy")
    object.__setattr__(policy.environment_pin, "backend_profile_id", "mutated-profile")
    object.__setattr__(
        policy.environment_pin,
        "container_digest",
        "sha256:" + "f" * 64,
    )

    submission_id = service.submit(requester, challenge, _strategy())
    original_id = submission_id.value
    object.__setattr__(requester, "value", "mutated-input-requester")
    object.__setattr__(challenge, "challenge_id", "a7_mutated")
    object.__setattr__(challenge, "version", "fixture-9.0")
    owned_requester = RequesterIdentity("owned-input-requester")
    validated = service.mark_validated(SubmissionId(original_id), owned_requester)
    object.__setattr__(validated.submission_id, "value", "invalid-view-id")
    object.__setattr__(validated, "state", SubmissionState.REJECTED)
    queued = service.admit_fixture(SubmissionId(original_id), owned_requester)
    object.__setattr__(queued.submission_id, "value", "invalid-queued-view-id")
    object.__setattr__(queued, "state", SubmissionState.CANCELLED)
    charge_key = FeeOperationKey("fixture-charge-op-v1")
    refund_key = FeeOperationKey("fixture-refund-op-v1")
    started = service.start_fixture_attempt(
        SubmissionId(original_id),
        owned_requester,
        charge_key,
        refund_key,
    )
    assert started.envelope is not None
    saved_handle = ExecutionAttemptHandle(
        submission_id=started.envelope.handle.submission_id,
        attempt_number=started.envelope.handle.attempt_number,
        admission_kind=started.envelope.handle.admission_kind,
        seed_pin=started.envelope.handle.seed_pin,
        environment_pin=started.envelope.handle.environment_pin,
    )
    object.__setattr__(charge_key, "value", "mutated-input-charge-key")
    object.__setattr__(refund_key, "value", "mutated-input-refund-key")
    object.__setattr__(submission_id, "value", "123e4567-e89b-42d3-a456-426614174001")
    object.__setattr__(started.fee_event.operation_key, "value", "mutated-event")
    object.__setattr__(started.fee_event.policy_key, "value", "mutated-event-policy")
    object.__setattr__(started.fee_event, "sequence", 99)
    object.__setattr__(started.fee_event, "kind", FeeEventKind.REFUND)
    object.__setattr__(
        started.fee_event,
        "operation_context",
        FeeOperationContext.TERMINAL_INFRA,
    )
    object.__setattr__(started.fee_event, "admission_kind", AdmissionKind.PRODUCTION)
    object.__setattr__(started.fee_event, "source_attempt_number", 99)
    object.__setattr__(
        started.fee_event,
        "charge_operation_key",
        FeeOperationKey("mutated-event-link"),
    )
    object.__setattr__(started.fee_event, "amount_minor", 999_999)
    object.__setattr__(
        started.envelope.handle.submission_id,
        "value",
        "123e4567-e89b-42d3-a456-426614174002",
    )
    object.__setattr__(started.envelope.handle, "attempt_number", 99)
    object.__setattr__(
        started.envelope.handle,
        "admission_kind",
        AdmissionKind.PRODUCTION,
    )
    object.__setattr__(
        started.envelope.handle.seed_pin,
        "generator_version",
        "mutated-generator",
    )
    object.__setattr__(
        started.envelope.handle.seed_pin,
        "generator_digest",
        "sha256:" + "f" * 64,
    )
    object.__setattr__(
        started.envelope.handle.seed_pin,
        "scoring_version",
        "mutated-scoring",
    )
    object.__setattr__(
        started.envelope.handle.seed_pin,
        "scoring_digest",
        "sha256:" + "f" * 64,
    )
    object.__setattr__(
        started.envelope.handle.seed_pin,
        "evaluation_binding",
        object(),
    )
    object.__setattr__(started.envelope.handle.seed_pin, "seed_scheme", "mutated")
    object.__setattr__(
        started.envelope.handle.seed_pin.challenge_key,
        "challenge_id",
        "a7_mutated",
    )
    object.__setattr__(
        started.envelope.handle.seed_pin.challenge_key,
        "version",
        "fixture-9.0",
    )
    object.__setattr__(
        started.envelope.handle.environment_pin,
        "backend_profile_id",
        "mutated-returned-profile",
    )
    object.__setattr__(
        started.envelope.handle.environment_pin,
        "container_digest",
        "sha256:" + "f" * 64,
    )
    started.envelope.strategy["challenge_id"] = "mutated"
    object.__setattr__(started.envelope.strategy_hash, "value", "mutated-hash")
    object.__setattr__(started.envelope.challenge_key, "challenge_id", "a7_mutated")
    object.__setattr__(started.envelope.challenge_key, "version", "fixture-9.0")
    object.__setattr__(started, "disposition", StartDisposition.ALREADY_STARTED)
    object.__setattr__(started, "state", SubmissionState.CANCELLED)
    object.__setattr__(started, "envelope", None)

    stored = service.get_status(SubmissionId(original_id), owned_requester)
    assert stored.state is SubmissionState.RUNNING
    object.__setattr__(stored.submission_id, "value", "invalid-status-id")
    object.__setattr__(stored, "state", SubmissionState.REJECTED)
    record = _record(service, SubmissionId(original_id))
    assert service._fixture_policy == _fixture_policy()
    assert record.requester_identity == RequesterIdentity("owned-input-requester")
    assert record.challenge_key == CHALLENGE_KEY
    assert record.fee_events[0].amount_minor == FIXTURE_AMOUNT
    assert record.fee_events[0].policy_key == FEE_POLICY_KEY
    assert record.fee_events[0].operation_key == FeeOperationKey("fixture-charge-op-v1")
    assert record.fee_events[0].sequence == 1
    assert record.fee_events[0].kind is FeeEventKind.CHARGE
    assert (
        record.fee_events[0].operation_context is FeeOperationContext.INITIAL_RUN_START
    )
    assert record.fee_events[0].admission_kind is AdmissionKind.FIXTURE
    assert record.fee_events[0].source_attempt_number == 1
    assert record.fee_events[0].charge_operation_key is None
    assert record.seed_pin.generator_version == GENERATOR_VERSION
    assert record.seed_pin.generator_digest == GENERATOR_DIGEST
    assert record.seed_pin.scoring_version == SCORING_VERSION
    assert record.seed_pin.scoring_digest == SCORING_DIGEST
    assert record.seed_pin.challenge_key == CHALLENGE_KEY
    assert type(record.seed_pin.evaluation_binding).__name__ == "EvaluationBinding"
    assert record.environment_pin == _environment_pin()
    assert record.current_handle == saved_handle
    assert record.seed_pin == saved_handle.seed_pin
    assert record.strategy["challenge_id"] == CHALLENGE_ID
    refund = service.fail_infrastructure(saved_handle)
    assert type(refund) is FeeEvent
    object.__setattr__(refund, "sequence", 99)
    object.__setattr__(refund.operation_key, "value", "mutated-refund")
    object.__setattr__(refund.policy_key, "value", "mutated-refund-policy")
    object.__setattr__(refund, "kind", FeeEventKind.RETRY_CREDIT)
    object.__setattr__(refund, "operation_context", FeeOperationContext.RETRY)
    object.__setattr__(refund, "admission_kind", AdmissionKind.PRODUCTION)
    object.__setattr__(refund, "source_attempt_number", 99)
    assert refund.charge_operation_key is not None
    object.__setattr__(refund.charge_operation_key, "value", "mutated-charge-link")
    object.__setattr__(refund, "amount_minor", 999_999)

    record = _record(service, SubmissionId(original_id))
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.fee_events[0].sequence == 1
    assert record.fee_events[0].amount_minor == FIXTURE_AMOUNT
    assert record.fee_events[0].operation_key == FeeOperationKey("fixture-charge-op-v1")
    assert record.fee_events[1].sequence == 2
    assert record.fee_events[1].amount_minor == FIXTURE_AMOUNT
    assert record.fee_events[1].operation_key == FeeOperationKey("fixture-refund-op-v1")
    assert record.fee_events[1].policy_key == FEE_POLICY_KEY
    assert record.fee_events[1].kind is FeeEventKind.REFUND
    assert record.fee_events[1].operation_context is FeeOperationContext.TERMINAL_INFRA
    assert record.fee_events[1].admission_kind is AdmissionKind.FIXTURE
    assert record.fee_events[1].source_attempt_number == 1
    assert record.fee_events[1].charge_operation_key == FeeOperationKey(
        "fixture-charge-op-v1"
    )


@pytest.mark.parametrize(
    "corruption",
    (
        "sequence",
        "operation",
        "policy",
        "amount",
        "kind",
        "context",
        "admission",
        "attempt",
        "link",
        "seed",
        "environment",
    ),
)
def test_initial_start_replay_rejects_corrupt_event_or_pins(
    tmp_path: Path,
    corruption: str,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    _start(service, submission_id)
    record = _record(service, submission_id)
    if corruption == "sequence":
        object.__setattr__(record.fee_events[0], "sequence", 2)
    elif corruption == "operation":
        object.__setattr__(
            record.fee_events[0],
            "operation_key",
            FeeOperationKey("corrupt-operation"),
        )
    elif corruption == "policy":
        object.__setattr__(
            record.fee_events[0],
            "policy_key",
            FeePolicyKey("corrupt-policy"),
        )
    elif corruption == "amount":
        object.__setattr__(record.fee_events[0], "amount_minor", FIXTURE_AMOUNT - 1)
    elif corruption == "kind":
        object.__setattr__(record.fee_events[0], "kind", FeeEventKind.REFUND)
    elif corruption == "context":
        object.__setattr__(
            record.fee_events[0],
            "operation_context",
            FeeOperationContext.TERMINAL_INFRA,
        )
    elif corruption == "admission":
        object.__setattr__(
            record.fee_events[0],
            "admission_kind",
            AdmissionKind.PRODUCTION,
        )
    elif corruption == "attempt":
        object.__setattr__(record.fee_events[0], "source_attempt_number", 2)
    elif corruption == "link":
        object.__setattr__(
            record.fee_events[0],
            "charge_operation_key",
            FeeOperationKey("corrupt-charge-link"),
        )
    elif corruption == "seed":
        object.__setattr__(record.seed_pin, "scoring_digest", "sha256:" + "f" * 64)
    else:
        object.__setattr__(
            record.environment_pin, "container_digest", "sha256:" + "f" * 64
        )

    with pytest.raises((SubmissionConflictError, SubmissionStoreError)):
        _start(service, submission_id)
    assert len(record.fee_events) == 1


@pytest.mark.parametrize(
    "corruption",
    (
        "sequence",
        "operation",
        "policy",
        "amount",
        "kind",
        "context",
        "link",
        "admission",
        "attempt",
    ),
)
def test_terminal_refund_replay_validates_complete_historical_event(
    tmp_path: Path,
    corruption: str,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.fail_infrastructure(started.envelope.handle)
    record = _record(service, submission_id)
    refund = record.fee_events[-1]
    replacement: object
    if corruption == "sequence":
        replacement = 7
    elif corruption == "operation":
        replacement = FeeOperationKey("wrong-refund-operation")
    elif corruption == "policy":
        replacement = FeePolicyKey("wrong-fee-policy")
    elif corruption == "amount":
        replacement = FIXTURE_AMOUNT - 1
    elif corruption == "kind":
        replacement = FeeEventKind.RETRY_CREDIT
    elif corruption == "context":
        replacement = FeeOperationContext.PUBLICATION_INFRA
    elif corruption == "link":
        replacement = FeeOperationKey("wrong-charge-link")
    elif corruption == "admission":
        replacement = AdmissionKind.PRODUCTION
    else:
        replacement = 2
    attribute = {
        "sequence": "sequence",
        "operation": "operation_key",
        "policy": "policy_key",
        "amount": "amount_minor",
        "kind": "kind",
        "context": "operation_context",
        "link": "charge_operation_key",
        "admission": "admission_kind",
        "attempt": "source_attempt_number",
    }[corruption]
    object.__setattr__(refund, attribute, replacement)

    with pytest.raises((SubmissionConflictError, SubmissionStoreError)):
        service.fail_infrastructure(started.envelope.handle)
    assert len(record.fee_events) == 2


def test_running_terminal_refund_replay_requires_historical_handle(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.fail_infrastructure(started.envelope.handle)

    with pytest.raises(SubmissionConflictError):
        service.fail_infrastructure(submission_id, REQUESTER)
    replay = service.fail_infrastructure(started.envelope.handle)
    assert type(replay) is FeeEvent
    assert len(_record(service, submission_id).fee_events) == 2


def test_publication_failure_plan_is_complete_before_scored_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    before = _lifecycle_snapshot(service, submission_id)
    original_make_refund = SubmissionService._make_refund_locked

    def fail_plan(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("injected publication failure-plan error")

    monkeypatch.setattr(SubmissionService, "_make_refund_locked", fail_plan)
    with pytest.raises(RuntimeError, match="injected publication failure-plan error"):
        service.complete_and_publish(started.envelope.handle, _result())

    assert _lifecycle_snapshot(service, submission_id) == before
    assert _record(service, submission_id).state is SubmissionState.RUNNING
    with pytest.raises(SubmissionStateError):
        service.read_published(submission_id, REQUESTER)

    monkeypatch.setattr(
        SubmissionService,
        "_make_refund_locked",
        original_make_refund,
    )
    published = service.complete_and_publish(started.envelope.handle, _result())
    assert published.state is SubmissionState.PUBLISHED


def test_a6_key_construction_failure_does_not_strand_scored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    def fail_key(value: object) -> object:
        del value
        raise ValueError("injected key adapter failure")

    monkeypatch.setattr(service_module, "CardRecordKey", fail_key)
    with pytest.raises((SubmissionIntegrationError, SubmissionStoreError)):
        service.complete_and_publish(started.envelope.handle, _result())

    record = _record(service, submission_id)
    assert record.state is SubmissionState.FAILED_INFRA
    assert record.fee_events[-1].kind is FeeEventKind.REFUND
    assert (
        record.fee_events[-1].operation_context is FeeOperationContext.PUBLICATION_INFRA
    )


def test_concurrent_initial_start_exact_replay_launches_once(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    barrier = threading.Barrier(2)
    results: list[InitialRunStartResult] = []
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait()
            results.append(_start(service, submission_id))
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            failures.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert {result.disposition for result in results} == {
        StartDisposition.STARTED,
        StartDisposition.ALREADY_STARTED,
    }
    assert sum(result.envelope is not None for result in results) == 1
    assert len(_record(service, submission_id).fee_events) == 1


def test_start_cancel_race_is_atomic_and_economically_consistent(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, object]] = []

    def start_worker() -> None:
        barrier.wait()
        try:
            outcomes.append(("start", _start(service, submission_id)))
        except Exception as error:  # noqa: BLE001
            outcomes.append(("start_error", error))

    def cancel_worker() -> None:
        barrier.wait()
        try:
            outcomes.append(("cancel", service.cancel(submission_id, REQUESTER)))
        except Exception as error:  # noqa: BLE001
            outcomes.append(("cancel_error", error))

    threads = [
        threading.Thread(target=start_worker),
        threading.Thread(target=cancel_worker),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    record = _record(service, submission_id)
    assert len(outcomes) == 2
    if record.state is SubmissionState.RUNNING:
        assert len(record.fee_events) == 1
        assert any(name == "start" for name, _ in outcomes)
        assert any(
            name == "cancel_error" and isinstance(value, SubmissionStateError)
            for name, value in outcomes
        )
    else:
        assert record.state is SubmissionState.CANCELLED
        assert record.fee_events == []
        assert any(name == "cancel" for name, _ in outcomes)
        assert any(
            name == "start_error" and isinstance(value, SubmissionStateError)
            for name, value in outcomes
        )


@pytest.mark.parametrize("charged_retry_queue", (False, True))
def test_queued_terminalization_cancel_race_has_one_terminal_and_exact_fees(
    tmp_path: Path,
    charged_retry_queue: bool,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    if charged_retry_queue:
        started = _start(service, submission_id)
        assert started.envelope is not None
        retried = service.retry_infrastructure(started.envelope.handle)
        assert type(retried) is SubmissionStatusView
        assert retried.state is SubmissionState.QUEUED

    barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def worker(operation: Callable[[], object]) -> None:
        barrier.wait()
        try:
            outcomes.append(operation())
        except Exception as error:  # noqa: BLE001
            outcomes.append(error)

    threads = [
        threading.Thread(
            target=worker,
            args=(lambda: service.cancel(submission_id, REQUESTER),),
        ),
        threading.Thread(
            target=worker,
            args=(lambda: service.fail_infrastructure(submission_id, REQUESTER),),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    record = _record(service, submission_id)
    assert len(outcomes) == 2
    assert sum(isinstance(value, SubmissionStateError) for value in outcomes) == 1
    assert record.state in {SubmissionState.CANCELLED, SubmissionState.FAILED_INFRA}
    if not charged_retry_queue:
        assert record.fee_events == []
    elif record.state is SubmissionState.CANCELLED:
        assert [event.kind for event in record.fee_events] == [FeeEventKind.CHARGE]
    else:
        assert [event.kind for event in record.fee_events] == [
            FeeEventKind.CHARGE,
            FeeEventKind.REFUND,
        ]
        assert record.fee_events[-1].source_attempt_number == 2


def test_strategy_infra_terminalization_race_has_one_terminal_and_valid_fees(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    handle = started.envelope.handle
    barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def worker(operation: Callable[[ExecutionAttemptHandle], object]) -> None:
        barrier.wait()
        try:
            outcomes.append(operation(handle))
        except Exception as error:  # noqa: BLE001
            outcomes.append(error)

    threads = [
        threading.Thread(target=worker, args=(service.fail_strategy,)),
        threading.Thread(target=worker, args=(service.fail_infrastructure,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    record = _record(service, submission_id)
    assert len(outcomes) == 2
    assert sum(isinstance(value, SubmissionStateError) for value in outcomes) == 1
    if record.state is SubmissionState.FAILED_STRATEGY:
        assert len(record.fee_events) == 1
    else:
        assert record.state is SubmissionState.FAILED_INFRA
        assert [event.kind for event in record.fee_events] == [
            FeeEventKind.CHARGE,
            FeeEventKind.REFUND,
        ]


@pytest.mark.parametrize(
    "terminal_state",
    (
        SubmissionState.PUBLISHED,
        SubmissionState.REJECTED,
        SubmissionState.FAILED_INFRA,
        SubmissionState.FAILED_STRATEGY,
        SubmissionState.CANCELLED,
    ),
)
def test_every_terminal_state_denies_cancellation_and_successors(
    tmp_path: Path,
    terminal_state: SubmissionState,
) -> None:
    service = _service(tmp_path / terminal_state.value.lower())
    historical_handle: ExecutionAttemptHandle | None = None
    if terminal_state is SubmissionState.REJECTED:
        submission_id = service.submit(REQUESTER, CHALLENGE_KEY, None)
        template_id = _submit_validate_admit(service)
        template = _record(service, template_id)
        historical_handle = ExecutionAttemptHandle(
            submission_id=submission_id,
            attempt_number=1,
            admission_kind=AdmissionKind.FIXTURE,
            seed_pin=template.seed_pin,
            environment_pin=template.environment_pin,
        )
    else:
        submission_id = service.submit(REQUESTER, CHALLENGE_KEY, _strategy())
        if terminal_state is SubmissionState.CANCELLED:
            service.mark_validated(submission_id, REQUESTER)
            service.admit_fixture(submission_id, REQUESTER)
            queued_record = _record(service, submission_id)
            historical_handle = ExecutionAttemptHandle(
                submission_id=queued_record.submission_id,
                attempt_number=queued_record.attempt_number,
                admission_kind=queued_record.admission_kind,
                seed_pin=queued_record.seed_pin,
                environment_pin=queued_record.environment_pin,
            )
            service.cancel(submission_id, REQUESTER)
        else:
            service.mark_validated(submission_id, REQUESTER)
            service.admit_fixture(submission_id, REQUESTER)
            if terminal_state is SubmissionState.FAILED_INFRA:
                queued_record = _record(service, submission_id)
                historical_handle = ExecutionAttemptHandle(
                    submission_id=queued_record.submission_id,
                    attempt_number=queued_record.attempt_number,
                    admission_kind=queued_record.admission_kind,
                    seed_pin=queued_record.seed_pin,
                    environment_pin=queued_record.environment_pin,
                )
                service.fail_infrastructure(submission_id, REQUESTER)
            else:
                started = _start(service, submission_id)
                assert started.envelope is not None
                historical_handle = started.envelope.handle
                if terminal_state is SubmissionState.FAILED_STRATEGY:
                    service.fail_strategy(started.envelope.handle)
                else:
                    service.complete_and_publish(started.envelope.handle, _result())

    assert service.get_status(submission_id, REQUESTER).state is terminal_state
    record = _record(service, submission_id)

    def snapshot() -> tuple[object, ...]:
        return (
            record.state,
            record.attempt_number,
            record.current_handle,
            tuple(record.attempt_events),
            tuple(record.fee_events),
            tuple(sorted(service._store.open_index.items())),
            service._store.retained_value_nodes,
            service._store.retained_strategy_identity_bytes,
        )

    ordinary_semantic_operations: tuple[Callable[[], object], ...] = (
        lambda: service.mark_validated(submission_id, REQUESTER),
        lambda: service.admit_fixture(submission_id, REQUESTER),
        lambda: service.admit_production(submission_id, REQUESTER),
        lambda: service.start_fixture_attempt(
            submission_id,
            REQUESTER,
            FeeOperationKey("terminal-new-charge"),
            FeeOperationKey("terminal-new-refund"),
        ),
        lambda: service.start_fixture_retry_attempt(submission_id, REQUESTER),
        lambda: service.fail_infrastructure(submission_id, REQUESTER),
        lambda: service.cancel(submission_id, REQUESTER),
    )
    for operation in ordinary_semantic_operations:
        before = snapshot()
        with pytest.raises(SubmissionStateError):
            operation()
        assert snapshot() == before

    unavailable_production_operations: tuple[Callable[[], object], ...] = (
        lambda: service.start_production_attempt(
            submission_id,
            REQUESTER,
            FeeOperationKey("terminal-production-charge"),
            FeeOperationKey("terminal-production-refund"),
        ),
        lambda: service.start_production_retry_attempt(submission_id, REQUESTER),
    )
    for operation in unavailable_production_operations:
        before = snapshot()
        with pytest.raises(SubmissionIntegrationError):
            operation()
        assert snapshot() == before

    if historical_handle is not None:
        handle_operations: tuple[Callable[[], object], ...] = (
            lambda: service.retry_infrastructure(historical_handle),
            lambda: service.fail_strategy(historical_handle),
            lambda: service.fail_infrastructure(historical_handle),
            lambda: service.complete_and_publish(historical_handle, _result()),
        )
        for operation in handle_operations:
            before = snapshot()
            with pytest.raises(SubmissionStateError):
                operation()
            assert snapshot() == before

    assert service.get_status(submission_id, REQUESTER).state is terminal_state


def test_fee_event_couplings_are_closed_and_owned() -> None:
    charge_key = FeeOperationKey("charge-operation")
    policy_key = FeePolicyKey("fixture-policy")
    charge = FeeEvent(
        sequence=1,
        operation_key=charge_key,
        policy_key=policy_key,
        kind=FeeEventKind.CHARGE,
        operation_context=FeeOperationContext.INITIAL_RUN_START,
        admission_kind=AdmissionKind.FIXTURE,
        source_attempt_number=1,
        amount_minor=0,
    )
    assert charge.operation_key == charge_key
    assert charge.operation_key is not charge_key
    assert charge.policy_key == policy_key
    assert charge.policy_key is not policy_key

    refund = FeeEvent(
        sequence=2,
        operation_key=FeeOperationKey("refund-operation"),
        policy_key=policy_key,
        kind=FeeEventKind.REFUND,
        operation_context=FeeOperationContext.TERMINAL_INFRA,
        admission_kind=AdmissionKind.FIXTURE,
        source_attempt_number=2,
        amount_minor=0,
        charge_operation_key=charge_key,
    )
    retry_credit = FeeEvent(
        sequence=3,
        operation_key=FeeOperationKey("future-retry-credit"),
        policy_key=policy_key,
        kind=FeeEventKind.RETRY_CREDIT,
        operation_context=FeeOperationContext.RETRY,
        admission_kind=AdmissionKind.FIXTURE,
        source_attempt_number=2,
        amount_minor=0,
        charge_operation_key=charge_key,
    )
    assert refund.charge_operation_key == charge_key
    assert retry_credit.kind is FeeEventKind.RETRY_CREDIT


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "kind": FeeEventKind.CHARGE,
            "operation_context": FeeOperationContext.RETRY,
            "charge_operation_key": None,
        },
        {
            "kind": FeeEventKind.CHARGE,
            "operation_context": FeeOperationContext.INITIAL_RUN_START,
            "charge_operation_key": FeeOperationKey("link"),
        },
        {
            "kind": FeeEventKind.REFUND,
            "operation_context": FeeOperationContext.TERMINAL_INFRA,
            "charge_operation_key": None,
        },
        {
            "kind": FeeEventKind.RETRY_CREDIT,
            "operation_context": FeeOperationContext.TERMINAL_INFRA,
            "charge_operation_key": FeeOperationKey("link"),
        },
    ),
)
def test_invalid_fee_event_coupling_rejects(kwargs: dict[str, object]) -> None:
    with pytest.raises(SubmissionIntegrationError):
        FeeEvent(
            sequence=1,
            operation_key=FeeOperationKey("operation"),
            policy_key=FeePolicyKey("policy"),
            admission_kind=AdmissionKind.FIXTURE,
            source_attempt_number=1,
            amount_minor=1,
            **kwargs,  # type: ignore[arg-type]
        )


def test_current_wave_never_emits_retry_credit_or_retry_context(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    first = _start(service, submission_id)
    assert first.envelope is not None
    service.retry_infrastructure(first.envelope.handle)
    second = service.start_fixture_retry_attempt(submission_id, REQUESTER)
    service.fail_infrastructure(second.handle)

    events = _record(service, submission_id).fee_events
    assert all(event.kind is not FeeEventKind.RETRY_CREDIT for event in events)
    assert all(
        event.operation_context is not FeeOperationContext.RETRY for event in events
    )
    for forbidden_method in (
        "adjust_fee",
        "refund",
        "retry_credit",
        "append_fee_event",
        "set_state",
    ):
        assert not hasattr(service, forbidden_method)


@pytest.mark.parametrize("over_cap", (False, True))
def test_ledger_aggregate_adjustment_cap_and_remaining_balance(
    tmp_path: Path,
    over_cap: bool,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    record = _record(service, submission_id)
    credit_amount = FIXTURE_AMOUNT + 1 if over_cap else 103
    record.fee_events.append(
        FeeEvent(
            sequence=2,
            operation_key=FeeOperationKey("future-credit-operation"),
            policy_key=FEE_POLICY_KEY,
            kind=FeeEventKind.RETRY_CREDIT,
            operation_context=FeeOperationContext.RETRY,
            admission_kind=AdmissionKind.FIXTURE,
            source_attempt_number=1,
            amount_minor=credit_amount,
            charge_operation_key=started.fee_event.operation_key,
        )
    )

    if over_cap:
        with pytest.raises(SubmissionStoreError):
            service.fail_infrastructure(started.envelope.handle)
        assert record.state is SubmissionState.RUNNING
        assert len(record.fee_events) == 2
    else:
        refund = service.fail_infrastructure(started.envelope.handle)
        assert type(refund) is FeeEvent
        assert refund.sequence == 3
        assert refund.amount_minor == FIXTURE_AMOUNT - credit_amount
        assert record.state is SubmissionState.FAILED_INFRA
        replay = service.fail_infrastructure(started.envelope.handle)
        assert replay == refund
        assert replay is not refund


def test_fixture_retry_cannot_cross_into_production_retry(tmp_path: Path) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.retry_infrastructure(started.envelope.handle)
    before = (
        list(_record(service, submission_id).attempt_events),
        list(_record(service, submission_id).fee_events),
    )

    with pytest.raises(SubmissionIntegrationError):
        service.start_production_retry_attempt(submission_id, REQUESTER)

    assert service.get_status(submission_id, REQUESTER).state is SubmissionState.QUEUED
    assert _record(service, submission_id).attempt_events == before[0]
    assert _record(service, submission_id).fee_events == before[1]


def test_private_record_is_minimal_safe_and_non_echoing(tmp_path: Path) -> None:
    strategy = _strategy(
        parameters={
            "public_fixture_note": "safe",
            "ordinary_value": 17,
        }
    )
    service = _service(tmp_path)
    submission_id = service.submit(REQUESTER, CHALLENGE_KEY, strategy)
    service.mark_validated(submission_id, REQUESTER)
    service.admit_fixture(submission_id, REQUESTER)
    started = _start(service, submission_id)
    assert started.envelope is not None
    service.complete_and_publish(started.envelope.handle, _result())
    record = _record(service, submission_id)

    assert repr(service) == "<SubmissionService>"
    assert repr(record) == "<_SubmissionRecord>"
    field_names = {field.name for field in fields(record)}
    assert "strategy" in field_names
    assert "strategy_hash" in field_names
    forbidden_fragments = (
        "entropy",
        "private_root",
        "derived_seed",
        "draw",
        "realization",
        "prediction",
        "reference",
        "metric",
        "runtime_result",
        "runtime_status",
        "stack",
        "receipt",
        "evidence",
        "signature",
        "credential",
        "internal_result",
        "score_input",
        "emission",
        "diagnostic",
        "resource_limit",
        "observed",
    )
    assert not any(
        fragment in field_name
        for field_name in field_names
        for fragment in forbidden_fragments
    )
    assert not hasattr(record, "internal_result")
    assert not hasattr(record, "evaluation_card")


def test_handles_envelopes_and_service_do_not_support_generic_serialization(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    submission_id = _submit_validate_admit(service)
    started = _start(service, submission_id)
    assert started.envelope is not None

    for value in (started.envelope.handle, started.envelope, service):
        with pytest.raises((TypeError, ValueError, AttributeError)):
            pickle.dumps(value)
        with pytest.raises(TypeError):
            json.dumps(value)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        dataclasses.asdict(started.envelope.handle)


def test_fee_values_cannot_enter_a5_models_or_scoring_signature() -> None:
    forbidden = {"fee", "amount", "charge", "refund", "payment", "policy_key"}
    for model in (ScoreInput, ScorePackPin, InternalResult):
        assert not any(
            token in field.name.lower()
            for field in fields(model)
            for token in forbidden
        )
    signature = inspect.signature(ScoreEngine.score)
    assert tuple(signature.parameters) == ("score_input", "pack")
    assert not any(
        token in parameter.lower()
        for parameter in signature.parameters
        for token in forbidden
    )


def test_public_exports_are_exact_and_no_private_store_surface_exists(
    tmp_path: Path,
) -> None:
    assert set(fees.__all__) == set(PUBLIC_EXPORTS)
    service = _service(tmp_path)
    public_members = {name for name in dir(service) if not name.startswith("_")}
    assert public_members == {
        "admit_fixture",
        "admit_production",
        "cancel",
        "complete_and_publish",
        "fail_infrastructure",
        "fail_strategy",
        "get_status",
        "mark_validated",
        "read_published",
        "retry_infrastructure",
        "start_fixture_attempt",
        "start_fixture_retry_attempt",
        "start_production_attempt",
        "start_production_retry_attempt",
        "submit",
    }
    for forbidden in (
        "records",
        "card_store",
        "fee_events",
        "attempt_history",
        "get_strategy",
        "get_record",
        "get_seed_pin",
    ):
        assert not hasattr(service, forbidden)


def test_a7_source_import_graph_excludes_a8_and_later_owners() -> None:
    forbidden_modules = {
        "bittensor",
        "carbon.audit",
        "carbon.backbones",
        "carbon.chain",
        "carbon.emission",
        "carbon.evaluation",
        "carbon.leaderboard",
        "carbon.logging_utils",
        "carbon.mcp",
        "carbon.traineval",
        "carbon.training",
        "carbon.validator",
        "docker",
        "jax",
        "numpy",
        "physicsnemo",
        "torch",
    }
    for path in sorted((REPOSITORY_ROOT / "carbon/fees").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        assert not any(
            module == forbidden or module.startswith(forbidden + ".")
            for module in imported
            for forbidden in forbidden_modules
        ), path


def test_a7_import_isolated_from_optional_and_later_modules(tmp_path: Path) -> None:
    script = f"""
import importlib.abc
import json
import pathlib
import sys

blocked = {json.dumps(sorted({
    "bittensor", "docker", "jax", "numpy", "physicsnemo", "torch",
    "carbon.audit", "carbon.backbones", "carbon.chain", "carbon.emission",
    "carbon.evaluation", "carbon.leaderboard", "carbon.logging_utils",
    "carbon.mcp", "carbon.traineval", "carbon.training", "carbon.validator",
}))}

def is_blocked(fullname):
    return any(fullname == name or fullname.startswith(name + ".") for name in blocked)

class Blocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if is_blocked(fullname):
            self.attempted.append(fullname)
            raise ModuleNotFoundError("blocked A7 import", name=fullname)
        return None

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})
blocker = Blocker()
sys.meta_path.insert(0, blocker)
import carbon.fees as fees
loaded = sorted(name for name in sys.modules if is_blocked(name))
print(json.dumps({{
    "attempted": blocker.attempted,
    "exports": sorted(fees.__all__),
    "loaded": loaded,
    "module_file": str(pathlib.Path(fees.__file__).resolve()),
}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "attempted": [],
        "exports": sorted(PUBLIC_EXPORTS),
        "loaded": [],
        "module_file": str((REPOSITORY_ROOT / "carbon/fees/__init__.py").resolve()),
    }


def _copy_wheel_source(destination: Path) -> None:
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", destination)
    shutil.copy2(REPOSITORY_ROOT / "README.md", destination)
    shutil.copytree(
        REPOSITORY_ROOT / "carbon",
        destination / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )


def _offline_wheel_builder() -> str | None:
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
            return candidate
    return None


def test_fresh_wheel_imports_a7_outside_tree_without_dependencies(
    tmp_path: Path,
) -> None:
    build_source = tmp_path / "fresh-source"
    wheelhouse = tmp_path / "wheelhouse"
    environment = tmp_path / "environment"
    outside = tmp_path / "outside"
    subprocess_tmp = tmp_path / "subprocess-tmp"
    for directory in (build_source, wheelhouse, outside, subprocess_tmp):
        directory.mkdir()
    _copy_wheel_source(build_source)
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
        cwd=outside,
        env=install_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install_result.returncode == 0, install_result.stderr

    script = textwrap.dedent("""
        import importlib.metadata
        import json
        import pathlib
        from carbon import fees
        from carbon.fees import SubmissionResourceLimits

        limits = SubmissionResourceLimits(*([7] * 11))
        distribution = importlib.metadata.distribution("carbon")
        print(json.dumps({
            "distribution": [distribution.metadata["Name"], distribution.version],
            "exports": sorted(fees.__all__),
            "fields": [field for field in limits.__slots__],
            "module_file": str(pathlib.Path(fees.__file__).resolve()),
        }))
        """)
    execution = subprocess.run(
        [str(environment_python), "-I", "-c", script],
        cwd=outside,
        env=install_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert execution.returncode == 0, execution.stderr
    payload = json.loads(execution.stdout)
    module_file = Path(payload.pop("module_file"))
    assert REPOSITORY_ROOT not in module_file.parents
    assert build_source not in module_file.parents
    assert outside not in module_file.parents
    assert environment in module_file.parents
    assert payload == {
        "distribution": ["carbon", "0.9.0"],
        "exports": sorted(PUBLIC_EXPORTS),
        "fields": list(LIMIT_FIELDS),
    }
