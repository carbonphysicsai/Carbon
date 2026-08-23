"""CPU acceptance tests for the bounded A8 fixture-official TrainEval stub."""

from __future__ import annotations

import ast
import builtins
import copy
import dataclasses
import gc
import hashlib
import hmac
import inspect
import json
import os
import pickle
import random
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any

import pytest

from carbon import traineval
from carbon.cards import EvaluationCard
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    ProductionExecutionEnvelope,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
    SubmissionResourceLimits,
    SubmissionService,
    SubmissionState,
    SubmissionStateError,
    SubmissionStatusView,
)
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationEvidence,
    QualificationManifest,
)
from carbon.scoring import (
    BooleanInput,
    LoadedScorePack,
    NumericInput,
    ScoreEngine,
    ScoreInput,
    load_score_pack,
)
from carbon.scoring.model import InternalResult, ScoreStatus
from carbon.seeding import (
    DerivedSeed,
    DeterministicFixtureProvider,
    EvaluationBinding,
    FixtureOfficialContext,
    FixtureOfficialEntropy,
    MockContext,
    MockEntropy,
    OfficialContext,
    OfficialEntropy,
    QualificationContext,
    QualificationEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
    acquire_fixture_official_context,
    acquire_official_context,
    derive_fixture_official_seed,
)
from carbon.traineval import service as service_module
from carbon.traineval.model import (
    CompletedFixtureRun,
    FixtureRunIdentityError,
    FixtureRunRequestError,
    FixtureRuntimePolicy,
    FixtureStubProfile,
    InfrastructureCause,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
    StrategyFailedRun,
    StrategyFailureCause,
)
from carbon.traineval.service import FixtureTrainEvalService
from carbon.traineval.stub import FixtureStubBackend, _FixtureBackendMaterial

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCORE_PACK_ROOT = REPOSITORY_ROOT / "tests/fixtures/score_packs"
SCORE_PACK_PATH = "a5_fixture_v1.json"
BACKEND_PROFILE_ID = "a8-fixture-backend-v1"
ALTERNATE_BACKEND_PROFILE_ID = "a8-fixture-backend-v2"
CONTAINER_DIGEST = "sha256:" + "2" * 64
ALTERNATE_CONTAINER_DIGEST = "sha256:" + "4" * 64
STRATEGY_DIGEST = "sha256:" + "3" * 64
ALTERNATE_STRATEGY_DIGEST = "sha256:" + "5" * 64
SUBMISSION_ID_TEXT = "123e4567-e89b-42d3-a456-426614174000"
FIXTURE_AMOUNT = 1703

PUBLIC_EXPORTS = (
    "FixtureRunIdentityError",
    "FixtureRunRequestError",
    "FixtureRuntimePolicy",
    "FixtureStubBackend",
    "FixtureStubProfile",
    "FixtureTrainEvalService",
)

NUMERIC_KEYS = (
    "gate_error",
    "diagnostic_error",
    "physics_error",
    "robust_mean_a",
    "robust_tail_a",
    "robust_mean_b",
    "robust_tail_b",
    "accuracy_error_a",
    "accuracy_error_b",
)
BOOLEAN_KEYS = ("finite_ok",)

GOLDEN_SCALARS = (
    ("gate_error", 0.7094521213001038),
    ("diagnostic_error", 0.561526760825363),
    ("physics_error", 0.2684064950535693),
    ("robust_mean_a", 0.3546882861729247),
    ("robust_tail_a", 0.5906734915643228),
    ("robust_mean_b", 0.26036655348458393),
    ("robust_tail_b", 0.36921600047237385),
    ("accuracy_error_a", 0.4567727163044595),
    ("accuracy_error_b", 0.4629509096593334),
)

GOLDEN_LEG_SCORES = (
    ("physics", 0.9819894883532646),
    ("robustness", 0.9155975916282358),
    ("accuracy", 0.6849994079355737),
)
GOLDEN_COMBINED_SCORE = 0.8947523571654831

_PHASE_REQUESTS = (
    (
        SeedDomain.OFFICIAL_TRAIN,
        "a8_fixture_train",
        "official_train",
        ("diagnostic_error",),
    ),
    (
        SeedDomain.OFFICIAL_EVAL,
        "a8_fixture_eval",
        "official_eval",
        (
            "gate_error",
            "physics_error",
            "accuracy_error_a",
            "accuracy_error_b",
        ),
    ),
    (
        SeedDomain.OFFICIAL_STRESS,
        "a8_fixture_stress",
        "official_stress",
        (
            "robust_mean_a",
            "robust_tail_a",
            "robust_mean_b",
            "robust_tail_b",
        ),
    ),
)


class _StringSubclass(str):
    pass


class _DictSubclass(dict[str, object]):
    pass


class _FloatSubclass(float):
    pass


class _FixtureEnvelopeSubclass(FixtureExecutionEnvelope):
    __slots__ = ()


class _HandleSubclass(ExecutionAttemptHandle):
    __slots__ = ()


class _SeedPinSubclass(SeedPin):
    __slots__ = ()


class _EnvironmentSubclass(ExecutionEnvironmentPin):
    __slots__ = ()


class _ChallengeKeySubclass(ChallengeKey):
    __slots__ = ()


class _StrategyHashSubclass(StrategyHash):
    __slots__ = ()


class _ProfileSubclass(FixtureStubProfile):
    __slots__ = ()


class _PolicySubclass(FixtureRuntimePolicy):
    __slots__ = ()


class _ProviderSubclass(DeterministicFixtureProvider):
    __slots__ = ()


class _BackendSubclass(FixtureStubBackend):
    __slots__ = ()


class _ServiceSubclass(FixtureTrainEvalService):
    __slots__ = ()


class _LoadedScorePackSubclass(LoadedScorePack):
    __slots__ = ()


class _InternalResultSubclass(InternalResult):
    __slots__ = ()


class _MaterialSubclass(_FixtureBackendMaterial):
    __slots__ = ()


class _CompletedRunSubclass(CompletedFixtureRun):
    __slots__ = ()


class _StrategyFailedRunSubclass(StrategyFailedRun):
    __slots__ = ()


class _InfrastructureFailedRunSubclass(InfrastructureFailedRun):
    __slots__ = ()


class _HostileValue:
    def __repr__(self) -> str:
        raise AssertionError("hostile repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile str was invoked")

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile hash was invoked")


class _HostileException(RuntimeError):
    def __repr__(self) -> str:
        raise AssertionError("hostile exception repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile exception str was invoked")


class _DerivedLike:
    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls = 0

    def as_backend_bytes(self) -> bytes:
        self.calls += 1
        return _fixed_material(b"a8-wrong-derived-like")

    def __repr__(self) -> str:
        raise AssertionError("wrong derived repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("wrong derived str was invoked")


class _OfficialProvider:
    def observe_entropy(self) -> OfficialEntropy:
        return OfficialEntropy(_fixed_material(b"a8-official-context-crossing"))


def _fixed_material(label: bytes) -> bytes:
    return hashlib.sha256(label).digest()


def _profile() -> FixtureStubProfile:
    return FixtureStubProfile()


def _environment(
    *,
    backend_profile_id: str = BACKEND_PROFILE_ID,
    container_digest: str = CONTAINER_DIGEST,
) -> ExecutionEnvironmentPin:
    return ExecutionEnvironmentPin(backend_profile_id, container_digest)


def _retry_mapping() -> (
    tuple[tuple[InfrastructureCause, InfrastructureRetryClass], ...]
):
    return tuple(
        (
            cause,
            (
                InfrastructureRetryClass.RETRYABLE
                if index % 2
                else InfrastructureRetryClass.NON_RETRYABLE
            ),
        )
        for index, cause in enumerate(InfrastructureCause)
    )


def _policy(
    *,
    environment: ExecutionEnvironmentPin | None = None,
    mapping: (
        tuple[tuple[InfrastructureCause, InfrastructureRetryClass], ...] | None
    ) = None,
) -> FixtureRuntimePolicy:
    selected = environment or _environment()
    return FixtureRuntimePolicy(
        backend_profile_id=selected.backend_profile_id,
        container_digest=selected.container_digest,
        cause_retry_classes=_retry_mapping() if mapping is None else mapping,
    )


def _provider(
    label: bytes = b"carbon.a8.test.fixture.entropy.v1",
) -> DeterministicFixtureProvider:
    return DeterministicFixtureProvider(FixtureOfficialEntropy(_fixed_material(label)))


def _pack(profile: FixtureStubProfile | None = None) -> LoadedScorePack:
    selected = profile or _profile()
    return load_score_pack(
        SCORE_PACK_ROOT,
        SCORE_PACK_PATH,
        selected.score_pack_pin(),
    )


def _seed_pin(
    *,
    profile: FixtureStubProfile | None = None,
    challenge_key: ChallengeKey | None = None,
    generator_version: str | None = None,
    generator_digest: str | None = None,
    scoring_version: str | None = None,
    scoring_digest: str | None = None,
    evaluation_binding: EvaluationBinding | None = None,
) -> SeedPin:
    selected = profile or _profile()
    return SeedPin(
        challenge_key=challenge_key or selected.challenge_key,
        generator_version=generator_version or selected.generator_version_required,
        generator_digest=generator_digest or selected.generator_digest_required,
        scoring_version=scoring_version or selected.scoring_version,
        scoring_digest=scoring_digest or selected.scoring_digest,
        evaluation_binding=evaluation_binding
        or EvaluationBinding(_fixed_material(b"carbon.a8.test.binding.v1")),
    )


def _handle(
    *,
    attempt_number: int = 1,
    admission_kind: AdmissionKind = AdmissionKind.FIXTURE,
    seed_pin: SeedPin | None = None,
    environment: ExecutionEnvironmentPin | None = None,
) -> ExecutionAttemptHandle:
    return ExecutionAttemptHandle(
        submission_id=SubmissionId(SUBMISSION_ID_TEXT),
        attempt_number=attempt_number,
        admission_kind=admission_kind,
        seed_pin=seed_pin or _seed_pin(),
        environment_pin=environment or _environment(),
    )


def _strategy(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "challenge_id": "a5_fixture",
        "backbone": "fno",
        "parameters": {"fixture_note": "conspicuously_non_scientific"},
    }
    value.update(overrides)
    return value


def _envelope(
    *,
    handle: ExecutionAttemptHandle | None = None,
    strategy: dict[str, object] | None = None,
    strategy_hash: StrategyHash | None = None,
    challenge_key: ChallengeKey | None = None,
) -> FixtureExecutionEnvelope:
    selected_handle = handle or _handle()
    return FixtureExecutionEnvelope(
        handle=selected_handle,
        strategy=_strategy() if strategy is None else strategy,
        strategy_hash=strategy_hash or StrategyHash(STRATEGY_DIGEST),
        challenge_key=challenge_key or selected_handle.seed_pin.challenge_key,
    )


def _backend(
    *,
    environment: ExecutionEnvironmentPin | None = None,
) -> FixtureStubBackend:
    selected = environment or _environment()
    return FixtureStubBackend(
        backend_profile_id=selected.backend_profile_id,
        container_digest=selected.container_digest,
    )


def _service(
    *,
    profile: FixtureStubProfile | None = None,
    provider: DeterministicFixtureProvider | None = None,
    score_pack: LoadedScorePack | None = None,
    policy: FixtureRuntimePolicy | None = None,
    declared_environment: ExecutionEnvironmentPin | None = None,
    backend: FixtureStubBackend | None = None,
) -> FixtureTrainEvalService:
    selected_profile = profile or _profile()
    selected_environment = declared_environment or _environment()
    return FixtureTrainEvalService(
        profile=selected_profile,
        provider=provider or _provider(),
        score_pack=score_pack or _pack(selected_profile),
        policy=policy or _policy(environment=selected_environment),
        declared_environment=selected_environment,
        backend=backend or _backend(environment=selected_environment),
    )


def _completed_result(
    pack: LoadedScorePack,
    *,
    gate_error: float = 0.25,
) -> InternalResult:
    values = {key: 0.25 for key in NUMERIC_KEYS}
    values["gate_error"] = gate_error
    score_input = pack.fixture_score_input(
        numeric_inputs=tuple(NumericInput(key, values[key]) for key in NUMERIC_KEYS),
        boolean_inputs=(BooleanInput("finite_ok", True),),
    )
    return ScoreEngine.score(score_input, pack)


def _valid_material(
    *,
    gate_error: float = 0.25,
) -> _FixtureBackendMaterial:
    values = dict(GOLDEN_SCALARS)
    values["gate_error"] = gate_error
    return _FixtureBackendMaterial(
        numeric_values=tuple((key, values[key]) for key in NUMERIC_KEYS),
        boolean_values=(("finite_ok", True),),
    )


def _independent_frame_ascii(value: str) -> bytes:
    payload = value.encode("ascii", errors="strict")
    return len(payload).to_bytes(4, "big") + payload


def _independent_scalar(
    *,
    key_material: bytes,
    profile_id: str,
    phase_label: str,
    input_key: str,
    scoring_digest: str,
    generator_digest: str,
    backend_profile_id: str,
    container_digest: str,
) -> float:
    message = b"carbon.a8.fixture-stub.scalar.v1" + b"".join(
        _independent_frame_ascii(value)
        for value in (
            profile_id,
            phase_label,
            input_key,
            scoring_digest,
            generator_digest,
            backend_profile_id,
            container_digest,
        )
    )
    digest = hmac.new(key_material, message, hashlib.sha256).digest()
    integer = int.from_bytes(digest[:8], "big") >> 11
    unit = integer / 2**53
    if input_key == "gate_error":
        return 0.5 + (1.0 * unit)
    return 0.125 + (0.5 * unit)


def _phase_seeds(
    provider: DeterministicFixtureProvider,
    pin: SeedPin,
) -> tuple[bytes, bytes, bytes]:
    context = acquire_fixture_official_context(provider, pin)
    train = derive_fixture_official_seed(
        context,
        SeedDomain.OFFICIAL_TRAIN,
        RoleKey("a8_fixture_train"),
        0,
    ).as_backend_bytes()
    evaluation = derive_fixture_official_seed(
        context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("a8_fixture_eval"),
        0,
    ).as_backend_bytes()
    stress = derive_fixture_official_seed(
        context,
        SeedDomain.OFFICIAL_STRESS,
        RoleKey("a8_fixture_stress"),
        0,
    ).as_backend_bytes()
    del context
    return train, evaluation, stress


def _independent_material(
    provider: DeterministicFixtureProvider,
    pin: SeedPin,
    environment: ExecutionEnvironmentPin,
    *,
    profile_id: str = "a8_fixture_stub_v1",
) -> tuple[tuple[str, float], ...]:
    train, evaluation, stress = _phase_seeds(provider, pin)
    phase_material = {
        "official_train": train,
        "official_eval": evaluation,
        "official_stress": stress,
    }
    by_key: dict[str, float] = {}
    try:
        for _, _, phase_label, input_keys in _PHASE_REQUESTS:
            for input_key in input_keys:
                by_key[input_key] = _independent_scalar(
                    key_material=phase_material[phase_label],
                    profile_id=profile_id,
                    phase_label=phase_label,
                    input_key=input_key,
                    scoring_digest=(
                        "sha256:"
                        "255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
                    ),
                    generator_digest="sha256:" + "1" * 64,
                    backend_profile_id=environment.backend_profile_id,
                    container_digest=environment.container_digest,
                )
        return tuple((key, by_key[key]) for key in NUMERIC_KEYS)
    finally:
        del train, evaluation, stress, phase_material


def _independent_one_scalar(
    provider: DeterministicFixtureProvider,
    pin: SeedPin,
    environment: ExecutionEnvironmentPin,
    *,
    domain: SeedDomain,
    role: str,
    phase_label: str,
    input_key: str,
    draw_index: int = 0,
    profile_id: str = "a8_fixture_stub_v1",
) -> float:
    context = acquire_fixture_official_context(provider, pin)
    key_material = derive_fixture_official_seed(
        context,
        domain,
        RoleKey(role),
        draw_index,
    ).as_backend_bytes()
    try:
        return _independent_scalar(
            key_material=key_material,
            profile_id=profile_id,
            phase_label=phase_label,
            input_key=input_key,
            scoring_digest=(
                "sha256:"
                "255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
            ),
            generator_digest="sha256:" + "1" * 64,
            backend_profile_id=environment.backend_profile_id,
            container_digest=environment.container_digest,
        )
    finally:
        del context, key_material


def _unsafe_copy_exact(value: object, **overrides: object) -> object:
    copied = object.__new__(type(value))
    for item in fields(value):
        field_value = overrides.get(item.name, getattr(value, item.name))
        object.__setattr__(copied, item.name, field_value)
    return copied


def _forged_enum_member(enum_type: type[Any], member: Any) -> Any:
    forged = str.__new__(enum_type, member.value)
    object.__setattr__(forged, "_name_", "FORGED_" + member.name)
    object.__setattr__(forged, "_value_", member.value)
    return forged


def _limits() -> SubmissionResourceLimits:
    return SubmissionResourceLimits(
        max_total_value_nodes=10_000,
        max_object_members=256,
        max_list_items=256,
        max_string_utf8_bytes=4096,
        max_object_key_utf8_bytes=512,
        max_strategy_identity_bytes=1_000_000,
        max_challenge_id_bytes=256,
        max_concurrent_identity_builds=8,
        max_retained_submission_records=64,
        max_retained_value_nodes=100_000,
        max_retained_strategy_identity_bytes=4_000_000,
    )


def _fixture_registry(root: Path) -> ChallengeRegistry:
    registry_root = root / "registry"
    artifact_root = root / "artifacts"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(registry_root, artifact_root)
    artifact_id = "a8_fixture_bundle"
    artifact_path = "a5_fixture/fixture-1.0/fixture/bundle.bin"
    content = b"A8 conspicuous non-scientific fixture artifact\n"
    target = artifact_root.joinpath(*artifact_path.split("/"))
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a8-fixture-only-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    registry.save(
        ChallengeRecord(
            challenge_id="a5_fixture",
            version="fixture-1.0",
            fixture_origin=True,
            status="fixture",
            allowed_backbones=("fno",),
            artifacts={artifact_id: ArtifactBinding(path=artifact_path, digest=digest)},
            qualification=QualificationManifest(
                challenge_id="a5_fixture",
                challenge_version="fixture-1.0",
                mode="fixture",
                slots=slots,
            ),
        )
    )
    return registry


def _a7_service(
    root: Path,
    *,
    max_attempts: int = 2,
    environment: ExecutionEnvironmentPin | None = None,
) -> SubmissionService:
    selected_environment = environment or _environment()
    profile = _profile()
    return SubmissionService(
        resource_limits=_limits(),
        registry=_fixture_registry(root),
        fixture_policy=FixtureSubmissionPolicy(
            fee_policy_key=FeePolicyKey("a8-fixture-fee-policy-v1"),
            amount_minor=FIXTURE_AMOUNT,
            max_attempts=max_attempts,
            generator_version=profile.generator_version_required,
            generator_digest=profile.generator_digest_required,
            scoring_version=profile.scoring_version,
            scoring_digest=profile.scoring_digest,
            environment_pin=selected_environment,
        ),
        _uuid_factory=lambda: uuid.UUID(SUBMISSION_ID_TEXT),
    )


def _start_a7(
    service: SubmissionService,
) -> tuple[SubmissionId, FixtureExecutionEnvelope]:
    requester = RequesterIdentity("a8-fixture-requester-v1")
    submission_id = service.submit(
        requester,
        ChallengeKey("a5_fixture", "fixture-1.0"),
        _strategy(),
    )
    service.mark_validated(submission_id, requester)
    service.admit_fixture(submission_id, requester)
    started = service.start_fixture_attempt(
        submission_id,
        requester,
        FeeOperationKey("a8-fixture-charge-v1"),
        FeeOperationKey("a8-fixture-refund-v1"),
    )
    assert type(started.envelope) is FixtureExecutionEnvelope
    return submission_id, started.envelope


def _a7_snapshot(
    service: SubmissionService,
    submission_id: SubmissionId,
) -> tuple[object, ...]:
    record = service._store.records[submission_id.value]
    return (
        record.state,
        record.attempt_number,
        record.current_handle,
        tuple(record.attempt_events),
        tuple(record.fee_events),
        tuple(sorted(service._store.open_index.items())),
    )


def _apply_outcome(
    service: SubmissionService,
    outcome: object,
) -> object:
    """Test-owned composition only; A8 intentionally has no integration module."""
    if type(outcome) is CompletedFixtureRun:
        return service.complete_and_publish(outcome.handle, outcome.internal_result)
    if type(outcome) is StrategyFailedRun:
        return service.fail_strategy(outcome.handle)
    if type(outcome) is InfrastructureFailedRun:
        if outcome.retry_class is InfrastructureRetryClass.RETRYABLE:
            return service.retry_infrastructure(outcome.handle)
        if outcome.retry_class is InfrastructureRetryClass.NON_RETRYABLE:
            return service.fail_infrastructure(outcome.handle)
    raise AssertionError("test composition received an unsupported outcome")


def _assert_infrastructure(
    outcome: object,
    cause: InfrastructureCause,
    policy: FixtureRuntimePolicy | None = None,
) -> InfrastructureFailedRun:
    assert type(outcome) is InfrastructureFailedRun
    assert outcome.cause is cause
    expected_policy = policy or _policy()
    assert outcome.retry_class is expected_policy.retry_class_for(cause)
    assert outcome.emission_capable is False
    return outcome


def test_exact_closed_models_profile_policy_and_capability() -> None:
    profile = _profile()
    environment = _environment()
    policy = _policy(environment=environment)
    backend = _backend(environment=environment)
    completed = CompletedFixtureRun(
        _handle(environment=environment),
        _completed_result(_pack()),
    )
    strategy_failed = StrategyFailedRun(
        _handle(environment=environment),
        StrategyFailureCause.STRATEGY_RUNTIME_FAILURE,
    )
    infrastructure_failed = InfrastructureFailedRun(
        _handle(environment=environment),
        InfrastructureRetryClass.RETRYABLE,
        InfrastructureCause.EXECUTION_TIMEOUT,
    )

    assert {item.value for item in InfrastructureRetryClass} == {
        "RETRYABLE",
        "NON_RETRYABLE",
    }
    assert {item.value for item in StrategyFailureCause} == {
        "STRATEGY_RUNTIME_FAILURE",
        "STRATEGY_TRAINING_FAILURE",
        "STRATEGY_NUMERICAL_FAILURE",
    }
    assert {item.value for item in InfrastructureCause} == {
        "CONFIGURATION_UNAVAILABLE",
        "SCORE_PACK_MISMATCH",
        "SCORE_PACK_NOT_READY",
        "CONTEXT_UNAVAILABLE",
        "ENVIRONMENT_MISMATCH",
        "BACKEND_UNAVAILABLE",
        "BACKEND_STARTUP_FAILURE",
        "EXECUTION_TIMEOUT",
        "RESOURCE_VIOLATION",
        "BACKEND_NUMERICAL_FAILURE",
        "REFERENCE_FAILURE",
        "INCOMPLETE_EXECUTION_MATERIAL",
        "SCORE_INPUT_FAILURE",
        "SCORE_COMPUTATION_FAILURE",
    }
    assert tuple(item.name for item in fields(profile)) == (
        "profile_id",
        "challenge_key",
        "scoring_version",
        "scoring_digest",
        "generator_version_required",
        "generator_digest_required",
        "schema_version",
        "numerical_profile",
        "fixture_origin",
        "numeric_input_keys",
        "boolean_input_keys",
    )
    assert tuple(item.name for item in fields(policy)) == (
        "policy_id",
        "backend_profile_id",
        "container_digest",
        "cause_retry_classes",
    )
    assert tuple(item.name for item in fields(backend)) == (
        "backend_profile_id",
        "container_digest",
    )
    assert tuple(item.name for item in fields(completed)) == (
        "handle",
        "internal_result",
    )
    assert tuple(item.name for item in fields(strategy_failed)) == (
        "handle",
        "cause",
    )
    assert tuple(item.name for item in fields(infrastructure_failed)) == (
        "handle",
        "retry_class",
        "cause",
    )
    assert profile.profile_id == "a8_fixture_stub_v1"
    assert profile.challenge_key == ChallengeKey("a5_fixture", "fixture-1.0")
    assert profile.scoring_version == "fixture-1.0"
    assert profile.scoring_digest == (
        "sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
    )
    assert profile.generator_version_required == "fixture-1.0"
    assert profile.generator_digest_required == "sha256:" + "1" * 64
    assert profile.schema_version == "1.0"
    assert profile.numerical_profile == "python_binary64_v1"
    assert profile.fixture_origin is True
    assert profile.numeric_input_keys == NUMERIC_KEYS
    assert profile.boolean_input_keys == BOOLEAN_KEYS
    assert policy.policy_id == "a8_fixture_stub_policy_v1"
    assert policy.execution_environment_pin() == environment
    assert profile.score_pack_pin() == _pack().pack_pin
    assert profile.score_pack_pin() is not profile.score_pack_pin()
    for value in (
        profile,
        policy,
        backend,
        completed,
        strategy_failed,
        infrastructure_failed,
    ):
        assert not hasattr(value, "__dict__")
        assert (
            value.emission_capable is False
            if hasattr(value, "emission_capable")
            else True
        )
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            value.emission_capable = True  # type: ignore[attr-defined,misc]


def test_service_contract_has_one_envelope_and_no_caller_capability_switch() -> None:
    run_parameters = inspect.signature(FixtureTrainEvalService.run_fixture).parameters
    constructor_parameters = inspect.signature(
        FixtureTrainEvalService.__init__
    ).parameters

    assert tuple(run_parameters) == ("self", "envelope")
    assert tuple(constructor_parameters) == (
        "self",
        "profile",
        "provider",
        "score_pack",
        "policy",
        "declared_environment",
        "backend",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for name, parameter in constructor_parameters.items()
        if name != "self"
    )
    service = _service()
    envelope = _envelope()
    with pytest.raises(TypeError):
        service.run_fixture(envelope, mode="fixture")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        FixtureStubProfile(emission_capable=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        FixtureStubBackend(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
            emission_capable=False,
        )  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        CompletedFixtureRun(
            _handle(),
            _completed_result(_pack()),
            emission_capable=False,
        )  # type: ignore[call-arg]


def test_nominal_a8_values_reject_subclass_construction() -> None:
    handle = _handle()
    result = _completed_result(_pack())
    environment = _environment()

    constructions: tuple[Callable[[], object], ...] = (
        _ProfileSubclass,
        lambda: _PolicySubclass(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
            cause_retry_classes=_retry_mapping(),
        ),
        lambda: _BackendSubclass(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
        ),
        lambda: _ServiceSubclass(
            profile=_profile(),
            provider=_provider(),
            score_pack=_pack(),
            policy=_policy(environment=environment),
            declared_environment=environment,
            backend=_backend(environment=environment),
        ),
        lambda: _CompletedRunSubclass(handle, result),
        lambda: _StrategyFailedRunSubclass(
            handle,
            StrategyFailureCause.STRATEGY_RUNTIME_FAILURE,
        ),
        lambda: _InfrastructureFailedRunSubclass(
            handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
        ),
    )
    for construct in constructions:
        with pytest.raises(FixtureRunRequestError):
            construct()


def test_stable_errors_are_fixed_non_echoing_and_take_no_diagnostics() -> None:
    contracts = (
        (
            FixtureRunRequestError,
            "traineval.fixture_request_invalid",
            "Fixture execution request is invalid.",
        ),
        (
            FixtureRunIdentityError,
            "traineval.fixture_identity_invalid",
            "Fixture execution identity is invalid.",
        ),
    )
    for error_type, code, message in contracts:
        error = error_type()
        assert type(error) is error_type
        assert error.code == code
        assert str(error) == message
        assert error.args == (message,)
        assert error.__cause__ is None
        assert error.__context__ is None
        with pytest.raises(TypeError):
            error_type("caller-diagnostic-canary")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "invalid",
    (
        (),
        list(_retry_mapping()),
        _retry_mapping()[:-1],
        (*_retry_mapping(), _retry_mapping()[0]),
        ((InfrastructureCause.EXECUTION_TIMEOUT,),),
        (("EXECUTION_TIMEOUT", InfrastructureRetryClass.RETRYABLE),),
        ((InfrastructureCause.EXECUTION_TIMEOUT, "RETRYABLE"),),
    ),
)
def test_runtime_policy_requires_one_exact_class_for_every_cause(
    invalid: object,
) -> None:
    with pytest.raises(FixtureRunRequestError):
        FixtureRuntimePolicy(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
            cause_retry_classes=invalid,  # type: ignore[arg-type]
        )


def test_runtime_policy_has_no_default_and_rejects_forged_enum_members() -> None:
    policy = _policy()
    assert policy.cause_retry_classes == tuple(
        (cause, policy.retry_class_for(cause)) for cause in InfrastructureCause
    )
    with pytest.raises(FixtureRunRequestError):
        policy.retry_class_for(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FixtureRuntimePolicy()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        FixtureRuntimePolicy(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
            cause_retry_classes=_retry_mapping(),
            emission_capable=False,
        )  # type: ignore[call-arg]

    forged_cause = _forged_enum_member(
        InfrastructureCause,
        InfrastructureCause.CONFIGURATION_UNAVAILABLE,
    )
    forged_mapping = (
        (forged_cause, _retry_mapping()[0][1]),
        *_retry_mapping()[1:],
    )
    with pytest.raises(FixtureRunRequestError):
        FixtureRuntimePolicy(
            backend_profile_id=BACKEND_PROFILE_ID,
            container_digest=CONTAINER_DIGEST,
            cause_retry_classes=forged_mapping,
        )


def test_outcomes_require_exact_types_and_canonical_enum_members() -> None:
    handle = _handle()
    result = _completed_result(_pack())
    result_subclass = _InternalResultSubclass(
        result.status,
        result.pack_pin,
        result.gate_decisions,
        result.leg_scores,
        result.combined_score,
        result.eligible_for_emission,
    )
    handle_subclass = _HandleSubclass(
        handle.submission_id,
        handle.attempt_number,
        handle.admission_kind,
        handle.seed_pin,
        handle.environment_pin,
    )
    with pytest.raises(FixtureRunRequestError):
        CompletedFixtureRun(handle, result_subclass)
    with pytest.raises(FixtureRunIdentityError):
        CompletedFixtureRun(handle_subclass, result)
    with pytest.raises(FixtureRunRequestError):
        CompletedFixtureRun(
            handle,
            InternalResult(
                ScoreStatus.PACK_NOT_READY,
                result.pack_pin,
                (),
                (),
                None,
                False,
            ),
        )
    with pytest.raises(FixtureRunRequestError):
        StrategyFailedRun(handle, "STRATEGY_RUNTIME_FAILURE")  # type: ignore[arg-type]
    with pytest.raises(FixtureRunRequestError):
        InfrastructureFailedRun(
            handle,
            "RETRYABLE",  # type: ignore[arg-type]
            InfrastructureCause.EXECUTION_TIMEOUT,
        )

    forged_strategy = _forged_enum_member(
        StrategyFailureCause,
        StrategyFailureCause.STRATEGY_RUNTIME_FAILURE,
    )
    forged_retry = _forged_enum_member(
        InfrastructureRetryClass,
        InfrastructureRetryClass.RETRYABLE,
    )
    forged_cause = _forged_enum_member(
        InfrastructureCause,
        InfrastructureCause.EXECUTION_TIMEOUT,
    )
    with pytest.raises(FixtureRunRequestError):
        StrategyFailedRun(handle, forged_strategy)
    with pytest.raises(FixtureRunRequestError):
        InfrastructureFailedRun(
            handle,
            forged_retry,
            InfrastructureCause.EXECUTION_TIMEOUT,
        )
    with pytest.raises(FixtureRunRequestError):
        InfrastructureFailedRun(
            handle,
            InfrastructureRetryClass.RETRYABLE,
            forged_cause,
        )


def test_completed_outcome_recursively_owns_the_a5_graph() -> None:
    source_handle = _handle()
    source_result = _completed_result(_pack())
    outcome = CompletedFixtureRun(source_handle, source_result)

    assert outcome.handle == source_handle
    assert outcome.handle is not source_handle
    assert outcome.handle.submission_id is not source_handle.submission_id
    assert outcome.handle.seed_pin is not source_handle.seed_pin
    assert outcome.handle.environment_pin is not source_handle.environment_pin
    assert outcome.internal_result == source_result
    assert outcome.internal_result is not source_result
    assert outcome.internal_result.pack_pin is not source_result.pack_pin
    assert (
        outcome.internal_result.pack_pin.challenge_key
        is not source_result.pack_pin.challenge_key
    )
    assert outcome.internal_result.gate_decisions is not source_result.gate_decisions
    assert outcome.internal_result.leg_scores is not source_result.leg_scores
    for owned, caller in zip(
        outcome.internal_result.gate_decisions,
        source_result.gate_decisions,
        strict=True,
    ):
        assert owned == caller
        assert owned is not caller
    for owned, caller in zip(
        outcome.internal_result.leg_scores,
        source_result.leg_scores,
        strict=True,
    ):
        assert owned == caller
        assert owned is not caller
        assert owned.components is not caller.components
        assert all(
            owned_component is not caller_component
            for owned_component, caller_component in zip(
                owned.components,
                caller.components,
                strict=True,
            )
        )

    expected = outcome.internal_result
    object.__setattr__(source_handle, "attempt_number", 99)
    object.__setattr__(source_result, "combined_score", 0.0)
    object.__setattr__(source_result.pack_pin, "scoring_version", "fixture-9.0")
    object.__setattr__(source_result.gate_decisions[0], "passed", False)
    object.__setattr__(source_result.leg_scores[0], "score", 0.0)
    assert outcome.handle.attempt_number == 1
    assert outcome.internal_result == expected


@pytest.mark.parametrize(
    "bad_dependency",
    ("profile", "provider", "score_pack", "policy", "environment", "backend"),
)
def test_service_constructor_rejects_wrong_and_subclassed_dependencies(
    bad_dependency: str,
) -> None:
    profile = _profile()
    environment = _environment()
    values: dict[str, object] = {
        "profile": profile,
        "provider": _provider(),
        "score_pack": _pack(profile),
        "policy": _policy(environment=environment),
        "declared_environment": environment,
        "backend": _backend(environment=environment),
    }
    subclass_types = {
        "profile": _ProfileSubclass,
        "provider": _ProviderSubclass,
        "score_pack": _LoadedScorePackSubclass,
        "policy": _PolicySubclass,
        "environment": _EnvironmentSubclass,
        "backend": _BackendSubclass,
    }
    target = (
        "declared_environment" if bad_dependency == "environment" else bad_dependency
    )
    values[target] = object.__new__(subclass_types[bad_dependency])
    with pytest.raises(FixtureRunRequestError):
        FixtureTrainEvalService(**values)  # type: ignore[arg-type]
    values[target] = object()
    with pytest.raises(FixtureRunRequestError):
        FixtureTrainEvalService(**values)  # type: ignore[arg-type]


def test_service_preflight_rejects_profile_pack_and_environment_mismatch() -> None:
    profile = _profile()
    environment = _environment()
    pack = _pack(profile)

    mutated_profile = _profile()
    object.__setattr__(mutated_profile, "profile_id", "a8_fixture_stub_v2")
    with pytest.raises(FixtureRunRequestError):
        _service(profile=mutated_profile, score_pack=pack)

    mismatched_pin = dataclasses.replace(
        profile.score_pack_pin(),
        scoring_version="fixture-2.0",
    )
    object.__setattr__(pack, "pack_pin", mismatched_pin)
    with pytest.raises(FixtureRunIdentityError):
        _service(score_pack=pack)

    alternate = _environment(backend_profile_id=ALTERNATE_BACKEND_PROFILE_ID)
    with pytest.raises(FixtureRunIdentityError):
        _service(
            policy=_policy(environment=alternate),
            declared_environment=environment,
            backend=_backend(environment=environment),
        )
    with pytest.raises(FixtureRunIdentityError):
        _service(
            policy=_policy(environment=environment),
            declared_environment=environment,
            backend=_backend(environment=alternate),
        )


def test_service_preflight_rejects_exact_uninitialized_a5_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = object.__new__(InternalResult)
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(lambda score_input, pack: malformed),
    )

    with pytest.raises(FixtureRunRequestError) as captured:
        _service()
    assert captured.value.code == "traineval.fixture_request_invalid"
    assert str(captured.value) == "Fixture execution request is invalid."


def test_service_owns_mutable_safe_configuration_values() -> None:
    profile = _profile()
    provider = _provider()
    environment = _environment()
    policy = _policy(environment=environment)
    backend = _backend(environment=environment)
    service = _service(
        profile=profile,
        provider=provider,
        policy=policy,
        declared_environment=environment,
        backend=backend,
    )
    envelope = _envelope()
    expected = service.run_fixture(envelope)

    object.__setattr__(profile, "profile_id", "a8_fixture_stub_v9")
    object.__setattr__(policy, "backend_profile_id", ALTERNATE_BACKEND_PROFILE_ID)
    object.__setattr__(environment, "backend_profile_id", ALTERNATE_BACKEND_PROFILE_ID)
    object.__setattr__(backend, "backend_profile_id", ALTERNATE_BACKEND_PROFILE_ID)
    assert service.run_fixture(envelope) == expected


@pytest.mark.parametrize(
    "case",
    (
        "object",
        "subclass",
        "production",
        "mock-context",
        "official-context",
        "qualification-context",
    ),
)
def test_run_boundary_rejects_wrong_subclass_and_cross_kind_requests(
    case: str,
) -> None:
    service = _service()
    envelope = _envelope()
    if case == "object":
        request: object = object()
    elif case == "subclass":
        request = _FixtureEnvelopeSubclass(
            envelope.handle,
            envelope.strategy,
            envelope.strategy_hash,
            envelope.challenge_key,
        )
    elif case == "production":
        production_handle = _handle(admission_kind=AdmissionKind.PRODUCTION)
        request = ProductionExecutionEnvelope(
            production_handle,
            envelope.strategy,
            envelope.strategy_hash,
            envelope.challenge_key,
        )
    elif case == "mock-context":
        request = MockContext(
            MockEntropy(_fixed_material(b"a8-mock-cross")), _seed_pin()
        )
    elif case == "official-context":
        request = acquire_official_context(_OfficialProvider(), _seed_pin())
    else:
        request = QualificationContext(
            QualificationEntropy(_fixed_material(b"a8-qualification-cross")),
            _seed_pin(),
        )

    with pytest.raises(FixtureRunRequestError) as captured:
        service.run_fixture(request)  # type: ignore[arg-type]
    assert captured.value.code == "traineval.fixture_request_invalid"
    assert str(captured.value) == "Fixture execution request is invalid."


@pytest.mark.parametrize(
    "case",
    (
        "missing-envelope",
        "missing-handle",
        "handle-subclass",
        "seed-pin-subclass",
        "environment-subclass",
        "malformed-handle",
        "challenge-key-subclass",
        "malformed-key",
        "contradiction",
    ),
)
def test_run_boundary_rejects_malformed_identity_without_echo(case: str) -> None:
    service = _service()
    envelope = _envelope()
    if case == "missing-envelope":
        malformed = object.__new__(FixtureExecutionEnvelope)
    elif case == "missing-handle":
        malformed = _unsafe_copy_exact(
            envelope, handle=object.__new__(ExecutionAttemptHandle)
        )
    elif case == "handle-subclass":
        malformed = _unsafe_copy_exact(
            envelope,
            handle=object.__new__(_HandleSubclass),
        )
    elif case == "seed-pin-subclass":
        malformed = _unsafe_copy_exact(
            envelope,
            handle=_unsafe_copy_exact(
                envelope.handle,
                seed_pin=object.__new__(_SeedPinSubclass),
            ),
        )
    elif case == "environment-subclass":
        malformed = _unsafe_copy_exact(
            envelope,
            handle=_unsafe_copy_exact(
                envelope.handle,
                environment_pin=object.__new__(_EnvironmentSubclass),
            ),
        )
    elif case == "malformed-handle":
        hostile_handle = _unsafe_copy_exact(
            envelope.handle,
            seed_pin=_HostileValue(),
        )
        malformed = _unsafe_copy_exact(envelope, handle=hostile_handle)
    elif case == "challenge-key-subclass":
        malformed = _unsafe_copy_exact(
            envelope,
            challenge_key=object.__new__(_ChallengeKeySubclass),
        )
    elif case == "malformed-key":
        malformed = _unsafe_copy_exact(
            envelope,
            challenge_key=object.__new__(ChallengeKey),
        )
    else:
        malformed = _unsafe_copy_exact(
            envelope,
            challenge_key=ChallengeKey("a5_fixture_other", "fixture-1.0"),
        )

    with pytest.raises(FixtureRunIdentityError) as captured:
        service.run_fixture(malformed)  # type: ignore[arg-type]
    assert captured.value.code == "traineval.fixture_identity_invalid"
    assert str(captured.value) == "Fixture execution identity is invalid."
    assert "hostile" not in repr(captured.value).lower()


def test_exact_fixture_envelope_with_cross_kind_handle_is_request_error() -> None:
    service = _service()
    envelope = _envelope()
    production = _handle(admission_kind=AdmissionKind.PRODUCTION)
    malformed = _unsafe_copy_exact(envelope, handle=production)

    with pytest.raises(FixtureRunRequestError):
        service.run_fixture(malformed)  # type: ignore[arg-type]


def test_strategy_and_independent_strategy_hash_are_never_observed() -> None:
    service = _service()
    first_strategy = {
        "schema_version": "1.0",
        "challenge_id": "first_deliberately_ignored_value",
        "backbone": _HostileValue(),
        "parameters": {"nested": [_HostileValue()]},
    }
    second_strategy = {
        "schema_version": "deliberately_different",
        "challenge_id": "second_deliberately_ignored_value",
        "backbone": {"nested": _HostileValue()},
        "parameters": _HostileValue(),
    }
    first = _envelope(
        strategy=first_strategy,
        strategy_hash=StrategyHash(STRATEGY_DIGEST),
    )
    second = _envelope(
        strategy=second_strategy,
        strategy_hash=StrategyHash(ALTERNATE_STRATEGY_DIGEST),
    )
    first_outcome = service.run_fixture(first)
    second_outcome = service.run_fixture(second)

    assert type(first_outcome) is CompletedFixtureRun
    assert type(second_outcome) is CompletedFixtureRun
    assert first_outcome.internal_result == second_outcome.internal_result


@pytest.mark.parametrize(
    "case",
    (
        "wrong-strategy",
        "strategy-subclass",
        "wrong-hash",
        "hash-subclass",
        "malformed-hash",
    ),
)
def test_malformed_nominal_strategy_fields_are_non_echoing_identity_errors(
    case: str,
) -> None:
    envelope = _envelope()
    if case == "wrong-strategy":
        malformed = _unsafe_copy_exact(envelope, strategy=_HostileValue())
    elif case == "strategy-subclass":
        malformed = _unsafe_copy_exact(envelope, strategy=_DictSubclass())
    elif case == "wrong-hash":
        malformed = _unsafe_copy_exact(envelope, strategy_hash=_HostileValue())
    elif case == "hash-subclass":
        malformed = _unsafe_copy_exact(
            envelope,
            strategy_hash=_StrategyHashSubclass(STRATEGY_DIGEST),
        )
    else:
        hostile_hash = object.__new__(StrategyHash)
        object.__setattr__(hostile_hash, "value", _HostileValue())
        malformed = _unsafe_copy_exact(envelope, strategy_hash=hostile_hash)

    with pytest.raises(FixtureRunIdentityError) as captured:
        _service().run_fixture(malformed)  # type: ignore[arg-type]
    assert captured.value.code == "traineval.fixture_identity_invalid"
    assert str(captured.value) == "Fixture execution identity is invalid."


def test_fixture_context_acquisition_and_exact_domain_role_draw_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    envelope = _envelope()
    acquisitions: list[tuple[type[object], SeedPin]] = []
    entropy_observations: list[DeterministicFixtureProvider] = []
    derivations: list[tuple[SeedDomain, str, int]] = []
    original_acquire = service_module.acquire_fixture_official_context
    original_derive = service_module.derive_fixture_official_seed
    original_fixture_entropy = DeterministicFixtureProvider.fixture_entropy

    def fixture_entropy_spy(
        observed_provider: DeterministicFixtureProvider,
    ) -> FixtureOfficialEntropy:
        entropy_observations.append(observed_provider)
        return original_fixture_entropy(observed_provider)

    def acquire_spy(
        observed_provider: DeterministicFixtureProvider,
        pin: SeedPin,
    ) -> FixtureOfficialContext:
        assert observed_provider is provider
        acquisitions.append((type(observed_provider), pin))
        return original_acquire(observed_provider, pin)

    def derive_spy(
        context: FixtureOfficialContext,
        domain: SeedDomain,
        role_key: RoleKey,
        draw_index: int,
    ) -> DerivedSeed:
        assert type(context) is FixtureOfficialContext
        derivations.append((domain, role_key.value, draw_index))
        return original_derive(context, domain, role_key, draw_index)

    monkeypatch.setattr(
        DeterministicFixtureProvider,
        "fixture_entropy",
        fixture_entropy_spy,
    )
    service = _service(provider=provider)
    assert entropy_observations == []
    monkeypatch.setattr(service_module, "acquire_fixture_official_context", acquire_spy)
    monkeypatch.setattr(service_module, "derive_fixture_official_seed", derive_spy)

    outcome = service.run_fixture(envelope)

    assert type(outcome) is CompletedFixtureRun
    assert acquisitions == [(DeterministicFixtureProvider, envelope.handle.seed_pin)]
    assert entropy_observations == [provider]
    assert derivations == [
        (SeedDomain.OFFICIAL_TRAIN, "a8_fixture_train", 0),
        (SeedDomain.OFFICIAL_EVAL, "a8_fixture_eval", 0),
        (SeedDomain.OFFICIAL_STRESS, "a8_fixture_stress", 0),
    ]


@pytest.mark.parametrize(
    "case",
    ("mock", "official", "qualification", "wrong", "mismatched-fixture"),
)
def test_context_kind_and_context_pin_crossing_fail_operationally(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    service = _service()
    envelope = _envelope()
    pin = envelope.handle.seed_pin
    if case == "mock":
        returned: object = MockContext(
            MockEntropy(_fixed_material(b"a8-mock-context-return")),
            pin,
        )
    elif case == "official":
        returned = acquire_official_context(_OfficialProvider(), pin)
    elif case == "qualification":
        returned = QualificationContext(
            QualificationEntropy(_fixed_material(b"a8-qualification-return")),
            pin,
        )
    elif case == "wrong":
        returned = object()
    else:
        mismatched_pin = _seed_pin(
            evaluation_binding=EvaluationBinding(
                _fixed_material(b"a8-mismatched-context-binding")
            )
        )
        returned = acquire_fixture_official_context(_provider(), mismatched_pin)

    monkeypatch.setattr(
        service_module,
        "acquire_fixture_official_context",
        lambda provider, supplied_pin: returned,
    )

    _assert_infrastructure(
        service.run_fixture(envelope),
        InfrastructureCause.CONTEXT_UNAVAILABLE,
    )


@pytest.mark.parametrize("case", ("raw-bytes", "derived-like"))
def test_wrong_derived_seed_return_is_context_failure_without_method_use(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    derived_like = _DerivedLike()
    returned: object = (
        _fixed_material(b"a8-raw-derived-return")
        if case == "raw-bytes"
        else derived_like
    )
    monkeypatch.setattr(
        service_module,
        "derive_fixture_official_seed",
        lambda *args, **kwargs: returned,
    )

    outcome = _service().run_fixture(_envelope())

    _assert_infrastructure(outcome, InfrastructureCause.CONTEXT_UNAVAILABLE)
    assert derived_like.calls == 0


def test_independent_oracle_and_literal_golden_vectors() -> None:
    profile = _profile()
    provider = _provider()
    environment = _environment()
    pin = _seed_pin(profile=profile)
    train, evaluation, stress = _phase_seeds(provider, pin)
    try:
        material = _backend(environment=environment)._execute_fixture(
            profile=profile,
            train_seed=train,
            eval_seed=evaluation,
            stress_seed=stress,
        )
    finally:
        del train, evaluation, stress

    independent = _independent_material(provider, pin, environment)
    assert material.numeric_values == independent
    assert material.numeric_values == GOLDEN_SCALARS
    assert material.boolean_values == (("finite_ok", True),)

    outcome = _service(
        profile=profile,
        provider=provider,
        declared_environment=environment,
    ).run_fixture(_envelope(handle=_handle(seed_pin=pin, environment=environment)))
    assert type(outcome) is CompletedFixtureRun
    result = outcome.internal_result
    assert result.status is ScoreStatus.SCORED
    assert tuple((leg.leg, leg.score) for leg in result.leg_scores) == GOLDEN_LEG_SCORES
    assert result.combined_score == GOLDEN_COMBINED_SCORE
    assert tuple(
        (decision.gate_id, decision.passed, decision.mandatory)
        for decision in result.gate_decisions
    ) == (
        ("synthetic_error_gate", True, True),
        ("synthetic_finite_gate", True, True),
        ("synthetic_optional_diagnostic", True, False),
    )
    assert result.eligible_for_emission is False


@pytest.mark.parametrize(
    "field_name",
    (
        "challenge_key",
        "generator_version",
        "generator_digest",
        "scoring_version",
        "scoring_digest",
        "evaluation_binding",
    ),
)
def test_every_seed_pin_identity_perturbation_changes_a4_material_and_fails_closed(
    field_name: str,
) -> None:
    provider = _provider()
    environment = _environment()
    baseline_pin = _seed_pin()
    overrides: dict[str, object] = {}
    if field_name == "challenge_key":
        overrides[field_name] = ChallengeKey("a5_fixture_other", "fixture-1.0")
    elif field_name == "generator_version":
        overrides[field_name] = "fixture-2.0"
    elif field_name == "generator_digest":
        overrides[field_name] = "sha256:" + "6" * 64
    elif field_name == "scoring_version":
        overrides[field_name] = "fixture-2.0"
    elif field_name == "scoring_digest":
        overrides[field_name] = "sha256:" + "7" * 64
    else:
        overrides[field_name] = EvaluationBinding(
            _fixed_material(b"a8-perturbed-evaluation-binding")
        )
    changed_pin = _seed_pin(**overrides)  # type: ignore[arg-type]

    baseline_scalar = _independent_one_scalar(
        provider,
        baseline_pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="physics_error",
    )
    changed_scalar = _independent_one_scalar(
        provider,
        changed_pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="physics_error",
    )
    assert changed_scalar != baseline_scalar

    service = _service(provider=provider)
    changed_handle = _handle(seed_pin=changed_pin)
    outcome = service.run_fixture(
        _envelope(
            handle=changed_handle,
            challenge_key=changed_pin.challenge_key,
        )
    )
    if field_name == "evaluation_binding":
        baseline = service.run_fixture(_envelope())
        assert type(outcome) is CompletedFixtureRun
        assert type(baseline) is CompletedFixtureRun
        assert outcome.internal_result != baseline.internal_result
    else:
        _assert_infrastructure(outcome, InfrastructureCause.SCORE_PACK_MISMATCH)


@pytest.mark.parametrize(
    ("backend_profile_id", "container_digest"),
    (
        (ALTERNATE_BACKEND_PROFILE_ID, CONTAINER_DIGEST),
        (BACKEND_PROFILE_ID, ALTERNATE_CONTAINER_DIGEST),
    ),
)
def test_each_environment_identity_field_is_checked_and_bound_into_material(
    backend_profile_id: str,
    container_digest: str,
) -> None:
    baseline_service = _service()
    baseline = baseline_service.run_fixture(_envelope())
    assert type(baseline) is CompletedFixtureRun

    alternate = _environment(
        backend_profile_id=backend_profile_id,
        container_digest=container_digest,
    )
    mismatched = baseline_service.run_fixture(
        _envelope(handle=_handle(environment=alternate))
    )
    _assert_infrastructure(mismatched, InfrastructureCause.ENVIRONMENT_MISMATCH)

    matching_service = _service(
        declared_environment=alternate,
        policy=_policy(environment=alternate),
        backend=_backend(environment=alternate),
    )
    matching = matching_service.run_fixture(
        _envelope(handle=_handle(environment=alternate))
    )
    assert type(matching) is CompletedFixtureRun
    assert matching.internal_result != baseline.internal_result


def test_profile_phase_and_input_key_are_independent_scalar_inputs() -> None:
    provider = _provider()
    pin = _seed_pin()
    environment = _environment()
    baseline = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="physics_error",
    )
    changed_profile = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="physics_error",
        profile_id="a8_fixture_stub_v2",
    )
    changed_phase = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_train",
        input_key="physics_error",
    )
    changed_key = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="diagnostic_error",
    )
    assert len({baseline, changed_profile, changed_phase, changed_key}) == 4

    unsupported = _profile()
    object.__setattr__(unsupported, "profile_id", "a8_fixture_stub_v2")
    with pytest.raises(FixtureRunRequestError):
        _backend()._execute_fixture(
            profile=unsupported,
            train_seed=_fixed_material(b"a8-profile-train"),
            eval_seed=_fixed_material(b"a8-profile-eval"),
            stress_seed=_fixed_material(b"a8-profile-stress"),
        )


@pytest.mark.parametrize(
    ("domain", "role", "draw_index"),
    (
        (SeedDomain.OFFICIAL_STRESS, "a8_fixture_eval", 0),
        (SeedDomain.OFFICIAL_EVAL, "a8_fixture_stress", 0),
        (SeedDomain.OFFICIAL_EVAL, "a8_fixture_eval", 1),
    ),
)
def test_a4_domain_role_and_draw_are_independent_derivation_inputs(
    domain: SeedDomain,
    role: str,
    draw_index: int,
) -> None:
    provider = _provider()
    pin = _seed_pin()
    environment = _environment()
    baseline = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=SeedDomain.OFFICIAL_EVAL,
        role="a8_fixture_eval",
        phase_label="official_eval",
        input_key="physics_error",
    )
    perturbed = _independent_one_scalar(
        provider,
        pin,
        environment,
        domain=domain,
        role=role,
        draw_index=draw_index,
        phase_label="official_eval",
        input_key="physics_error",
    )
    assert perturbed != baseline


def test_repeated_call_order_and_attempt_number_preserve_scientific_material() -> None:
    service = _service()
    first_envelope = _envelope(handle=_handle(attempt_number=1))
    first = service.run_fixture(first_envelope)
    second = service.run_fixture(first_envelope)
    assert type(first) is CompletedFixtureRun
    assert type(second) is CompletedFixtureRun
    assert first == second
    assert first is not second
    assert first.handle is not second.handle
    assert first.internal_result is not second.internal_result

    unrelated_pin = _seed_pin(
        evaluation_binding=EvaluationBinding(_fixed_material(b"a8-call-order-binding"))
    )
    service.run_fixture(_envelope(handle=_handle(seed_pin=unrelated_pin)))
    assert service.run_fixture(first_envelope) == first

    retry = service.run_fixture(_envelope(handle=_handle(attempt_number=2)))
    assert type(retry) is CompletedFixtureRun
    assert retry.handle.attempt_number == 2
    assert retry.handle != first.handle
    assert retry.internal_result == first.internal_result


def test_concurrent_repeated_execution_is_stateless_and_equal() -> None:
    service = _service()
    envelope = _envelope()
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(service.run_fixture, (envelope,) * 8))

    assert all(type(outcome) is CompletedFixtureRun for outcome in outcomes)
    assert all(outcome == outcomes[0] for outcome in outcomes)
    assert len({id(outcome) for outcome in outcomes}) == len(outcomes)


def test_no_ambient_hash_time_random_filesystem_network_or_environment_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    envelope = _envelope()
    expected = service.run_fixture(envelope)

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("ambient dependency was used")

    monkeypatch.setattr(builtins, "hash", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(random, "random", forbidden)
    monkeypatch.setattr(random, "getrandbits", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "time_ns", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(Path, "iterdir", forbidden)
    monkeypatch.setenv("CARBON_A8_AMBIENT_CANARY", "must-not-be-read")

    assert service.run_fixture(envelope) == expected


@pytest.mark.parametrize(
    "case",
    (
        "wrong-object",
        "subclass",
        "numeric-list",
        "boolean-list",
        "missing-numeric",
        "extra-numeric",
        "wrong-key",
        "wrong-entry-container",
        "integer-value",
        "float-subclass",
        "nan",
        "positive-infinity",
        "negative-value",
        "missing-boolean",
        "extra-boolean",
        "false-finite",
        "wrong-boolean-type",
        "amplified",
    ),
)
def test_malformed_incomplete_nonfinite_and_amplified_backend_material_is_infra(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    valid = _valid_material()
    if case == "wrong-object":
        returned: object = object()
    elif case == "subclass":
        returned = _MaterialSubclass(valid.numeric_values, valid.boolean_values)
    elif case == "numeric-list":
        returned = _unsafe_copy_exact(valid, numeric_values=list(valid.numeric_values))
    elif case == "boolean-list":
        returned = _unsafe_copy_exact(valid, boolean_values=list(valid.boolean_values))
    elif case == "missing-numeric":
        returned = _unsafe_copy_exact(valid, numeric_values=valid.numeric_values[:-1])
    elif case == "extra-numeric":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(*valid.numeric_values, ("extra", 0.25)),
        )
    elif case == "wrong-key":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(("wrong_key", 0.25), *valid.numeric_values[1:]),
        )
    elif case == "wrong-entry-container":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(["gate_error", 0.25], *valid.numeric_values[1:]),
        )
    elif case == "integer-value":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(("gate_error", 1), *valid.numeric_values[1:]),
        )
    elif case == "float-subclass":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(
                ("gate_error", _FloatSubclass(0.25)),
                *valid.numeric_values[1:],
            ),
        )
    elif case == "nan":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(("gate_error", float("nan")), *valid.numeric_values[1:]),
        )
    elif case == "positive-infinity":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(("gate_error", float("inf")), *valid.numeric_values[1:]),
        )
    elif case == "negative-value":
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=(("gate_error", -0.25), *valid.numeric_values[1:]),
        )
    elif case == "missing-boolean":
        returned = _unsafe_copy_exact(valid, boolean_values=())
    elif case == "extra-boolean":
        returned = _unsafe_copy_exact(
            valid,
            boolean_values=(*valid.boolean_values, ("extra", True)),
        )
    elif case == "false-finite":
        returned = _unsafe_copy_exact(
            valid,
            boolean_values=(("finite_ok", False),),
        )
    elif case == "wrong-boolean-type":
        returned = _unsafe_copy_exact(
            valid,
            boolean_values=(("finite_ok", 1),),
        )
    else:
        returned = _unsafe_copy_exact(
            valid,
            numeric_values=tuple(("gate_error", 0.25) for _ in range(128)),
        )

    monkeypatch.setattr(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: returned,
    )
    outcome = _service().run_fixture(_envelope())
    _assert_infrastructure(
        outcome,
        InfrastructureCause.INCOMPLETE_EXECUTION_MATERIAL,
    )
    assert not isinstance(outcome, CompletedFixtureRun)


def test_complete_material_uses_only_a5_validated_input_and_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    original_input = LoadedScorePack.fixture_score_input
    original_score = ScoreEngine.score
    input_calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    score_calls: list[tuple[type[object], bool]] = []

    def input_spy(
        pack: LoadedScorePack,
        *,
        numeric_inputs: tuple[NumericInput, ...],
        boolean_inputs: tuple[BooleanInput, ...],
    ) -> ScoreInput:
        input_calls.append(
            (
                tuple(item.key for item in numeric_inputs),
                tuple(item.key for item in boolean_inputs),
            )
        )
        return original_input(
            pack,
            numeric_inputs=numeric_inputs,
            boolean_inputs=boolean_inputs,
        )

    def score_spy(score_input: ScoreInput, pack: LoadedScorePack) -> InternalResult:
        score_calls.append((type(score_input), type(pack) is LoadedScorePack))
        return original_score(score_input, pack)

    monkeypatch.setattr(LoadedScorePack, "fixture_score_input", input_spy)
    monkeypatch.setattr(ScoreEngine, "score", staticmethod(score_spy))

    outcome = service.run_fixture(_envelope())

    assert type(outcome) is CompletedFixtureRun
    assert input_calls == [(NUMERIC_KEYS, BOOLEAN_KEYS)]
    assert score_calls == [(ScoreInput, True)]


@pytest.mark.parametrize("case", ("wrong-object", "uninitialized", "forged"))
def test_invalid_nonraising_a5_factory_handoff_is_score_input_failure(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    pack = _pack()
    service = _service(score_pack=pack)

    def invalid_factory(
        supplied_pack: LoadedScorePack,
        *,
        numeric_inputs: tuple[NumericInput, ...],
        boolean_inputs: tuple[BooleanInput, ...],
    ) -> object:
        assert supplied_pack is pack
        if case == "wrong-object":
            return object()
        invalid = object.__new__(ScoreInput)
        if case == "uninitialized":
            return invalid
        changed_numeric = (
            NumericInput(numeric_inputs[0].key, numeric_inputs[0].value + 0.125),
            *numeric_inputs[1:],
        )
        object.__setattr__(invalid, "pack_pin", pack.pack_pin)
        object.__setattr__(invalid, "numeric_inputs", changed_numeric)
        object.__setattr__(invalid, "boolean_inputs", boolean_inputs)
        return invalid

    monkeypatch.setattr(LoadedScorePack, "fixture_score_input", invalid_factory)

    outcome = service.run_fixture(_envelope())

    _assert_infrastructure(outcome, InfrastructureCause.SCORE_INPUT_FAILURE)
    assert not hasattr(outcome, "internal_result")


def test_completed_scored_and_mandatory_gate_failure_are_distinct_valid_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scored_service = _service()
    scored = scored_service.run_fixture(_envelope())
    assert type(scored) is CompletedFixtureRun
    assert scored.internal_result.status is ScoreStatus.SCORED

    monkeypatch.setattr(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: _valid_material(gate_error=1.25),
    )
    gate_failed = _service().run_fixture(_envelope())
    assert type(gate_failed) is CompletedFixtureRun
    assert gate_failed.internal_result.status is ScoreStatus.MANDATORY_GATE_FAILED
    assert gate_failed.internal_result.combined_score == 0.0
    assert gate_failed.internal_result.leg_scores == ()
    assert any(
        decision.mandatory and not decision.passed
        for decision in gate_failed.internal_result.gate_decisions
    )


def test_pack_not_ready_is_operational_and_never_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _pack()
    service = _service(score_pack=pack)
    object.__setattr__(pack, "ready", False)
    pack_not_ready = InternalResult(
        ScoreStatus.PACK_NOT_READY,
        pack.pack_pin,
        (),
        (),
        None,
        False,
    )
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(lambda score_input, supplied_pack: pack_not_ready),
    )

    outcome = service.run_fixture(_envelope())

    _assert_infrastructure(outcome, InfrastructureCause.SCORE_PACK_NOT_READY)
    assert not hasattr(outcome, "internal_result")


def test_unready_pack_with_exact_uninitialized_a5_result_is_computation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _pack()
    service = _service(score_pack=pack)
    object.__setattr__(pack, "ready", False)
    malformed = object.__new__(InternalResult)
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(lambda score_input, supplied_pack: malformed),
    )

    outcome = service.run_fixture(_envelope())

    _assert_infrastructure(
        outcome,
        InfrastructureCause.SCORE_COMPUTATION_FAILURE,
    )
    assert not hasattr(outcome, "internal_result")


@pytest.mark.parametrize(
    "case",
    (
        "wrong-object",
        "subclass",
        "hostile-status",
        "forged-status",
        "emission-true",
        "mismatched-pack",
        "hostile-pack",
        "gate-list",
        "nonfinite-score",
    ),
)
def test_malformed_engine_results_fail_closed_without_hostile_operations(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    pack = _pack()
    service = _service(score_pack=pack)
    valid = _completed_result(pack)
    if case == "wrong-object":
        returned: object = object()
    elif case == "subclass":
        returned = _InternalResultSubclass(
            valid.status,
            valid.pack_pin,
            valid.gate_decisions,
            valid.leg_scores,
            valid.combined_score,
            valid.eligible_for_emission,
        )
    elif case == "hostile-status":
        returned = _unsafe_copy_exact(valid, status=_HostileValue())
    elif case == "forged-status":
        returned = _unsafe_copy_exact(
            valid,
            status=_forged_enum_member(ScoreStatus, ScoreStatus.SCORED),
        )
    elif case == "emission-true":
        returned = _unsafe_copy_exact(valid, eligible_for_emission=True)
    elif case == "mismatched-pack":
        returned = _unsafe_copy_exact(
            valid,
            pack_pin=dataclasses.replace(
                valid.pack_pin,
                scoring_version="fixture-2.0",
            ),
        )
    elif case == "hostile-pack":
        returned = _unsafe_copy_exact(valid, pack_pin=_HostileValue())
    elif case == "gate-list":
        returned = _unsafe_copy_exact(
            valid,
            gate_decisions=list(valid.gate_decisions),
        )
    else:
        returned = _unsafe_copy_exact(valid, combined_score=float("nan"))

    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(lambda score_input, supplied_pack: returned),
    )
    outcome = service.run_fixture(_envelope())

    _assert_infrastructure(
        outcome,
        InfrastructureCause.SCORE_COMPUTATION_FAILURE,
    )
    assert not hasattr(outcome, "internal_result")


def test_configuration_pack_environment_input_and_score_failures_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _pack()
    service = _service(score_pack=pack)
    object.__setattr__(pack, "pack_pin", object())
    _assert_infrastructure(
        service.run_fixture(_envelope()),
        InfrastructureCause.CONFIGURATION_UNAVAILABLE,
    )

    mismatched_pin = _seed_pin(scoring_version="fixture-2.0")
    _assert_infrastructure(
        _service().run_fixture(_envelope(handle=_handle(seed_pin=mismatched_pin))),
        InfrastructureCause.SCORE_PACK_MISMATCH,
    )

    alternate_environment = _environment(
        backend_profile_id=ALTERNATE_BACKEND_PROFILE_ID
    )
    _assert_infrastructure(
        _service().run_fixture(
            _envelope(handle=_handle(environment=alternate_environment))
        ),
        InfrastructureCause.ENVIRONMENT_MISMATCH,
    )

    input_service = _service()
    monkeypatch.setattr(
        LoadedScorePack,
        "fixture_score_input",
        lambda self, **kwargs: (_ for _ in ()).throw(_HostileException()),
    )
    _assert_infrastructure(
        input_service.run_fixture(_envelope()),
        InfrastructureCause.SCORE_INPUT_FAILURE,
    )
    monkeypatch.undo()

    score_service = _service()
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(
            lambda *args, **kwargs: (_ for _ in ()).throw(_HostileException())
        ),
    )
    _assert_infrastructure(
        score_service.run_fixture(_envelope()),
        InfrastructureCause.SCORE_COMPUTATION_FAILURE,
    )


def test_hostile_backend_exception_is_redacted_and_defaults_to_infrastructure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise _HostileException()

    monkeypatch.setattr(FixtureStubBackend, "_execute_fixture", fail)
    outcome = service.run_fixture(_envelope())

    _assert_infrastructure(outcome, InfrastructureCause.BACKEND_UNAVAILABLE)
    assert repr(outcome) == "InfrastructureFailedRun(<private>)"
    assert not hasattr(outcome, "message")
    assert not hasattr(outcome, "exception")
    assert not hasattr(outcome, "diagnostic")


def test_fixture_service_never_emits_strategy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = (_service(), _service(), _service())
    normal = services[0].run_fixture(_envelope())
    monkeypatch.setattr(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError()),
    )
    failed = services[1].run_fixture(_envelope())
    monkeypatch.setattr(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: _unsafe_copy_exact(
            _valid_material(),
            numeric_values=(
                ("gate_error", float("nan")),
                *_valid_material().numeric_values[1:],
            ),
        ),
    )
    malformed = services[2].run_fixture(_envelope())

    assert type(normal) is CompletedFixtureRun
    assert type(failed) is InfrastructureFailedRun
    assert type(malformed) is InfrastructureFailedRun
    assert all(
        type(outcome) is not StrategyFailedRun
        for outcome in (normal, failed, malformed)
    )


def test_backend_material_and_engine_result_are_detached_before_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_material = _valid_material()
    source_result = _completed_result(_pack())
    service = _service()
    monkeypatch.setattr(
        FixtureStubBackend,
        "_execute_fixture",
        lambda self, **kwargs: source_material,
    )
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        staticmethod(lambda score_input, pack: source_result),
    )

    outcome = service.run_fixture(_envelope())
    assert type(outcome) is CompletedFixtureRun
    expected = outcome.internal_result
    object.__setattr__(source_material, "numeric_values", ())
    object.__setattr__(source_result, "combined_score", 0.0)
    object.__setattr__(source_result.pack_pin, "scoring_version", "fixture-9.0")

    assert outcome.internal_result == expected
    assert outcome.internal_result is not source_result
    assert outcome.internal_result.pack_pin is not source_result.pack_pin


def test_caller_envelope_mutation_cannot_change_returned_outcome() -> None:
    service = _service()
    envelope = _envelope()
    outcome = service.run_fixture(envelope)
    assert type(outcome) is CompletedFixtureRun
    expected_handle = _handle()
    expected_result = CompletedFixtureRun(
        outcome.handle,
        outcome.internal_result,
    ).internal_result

    object.__setattr__(envelope.handle, "attempt_number", 99)
    object.__setattr__(
        envelope.handle.environment_pin,
        "backend_profile_id",
        ALTERNATE_BACKEND_PROFILE_ID,
    )
    object.__setattr__(
        envelope.handle.seed_pin,
        "scoring_version",
        "fixture-9.0",
    )
    envelope.strategy["challenge_id"] = "mutated"
    object.__setattr__(envelope.strategy_hash, "value", ALTERNATE_STRATEGY_DIGEST)
    object.__setattr__(envelope.challenge_key, "challenge_id", "mutated")

    assert outcome.handle == expected_handle
    assert outcome.handle.attempt_number == 1
    assert outcome.internal_result == expected_result


def test_malformed_untrusted_request_cannot_mutate_real_a7_attempt(
    tmp_path: Path,
) -> None:
    a7 = _a7_service(tmp_path / "malformed-boundary")
    submission_id, envelope = _start_a7(a7)
    before = _a7_snapshot(a7, submission_id)
    malformed = _unsafe_copy_exact(
        envelope,
        challenge_key=ChallengeKey("a5_fixture_other", "fixture-1.0"),
    )

    with pytest.raises(FixtureRunIdentityError):
        _service().run_fixture(malformed)  # type: ignore[arg-type]

    assert _a7_snapshot(a7, submission_id) == before


def test_completed_outcome_maps_to_a7_publication_and_a6_false_emission(
    tmp_path: Path,
) -> None:
    a7 = _a7_service(tmp_path / "completed-a7")
    submission_id, envelope = _start_a7(a7)
    outcome = _service().run_fixture(envelope)
    assert type(outcome) is CompletedFixtureRun

    applied = _apply_outcome(a7, outcome)
    card = a7.read_published(
        submission_id,
        RequesterIdentity("a8-fixture-requester-v1"),
    )

    assert type(applied) is SubmissionStatusView
    assert applied.state is SubmissionState.PUBLISHED
    assert type(card) is EvaluationCard
    assert card.fixture_origin is True
    assert card.eligible_for_emission is False
    assert outcome.emission_capable is False


def test_both_a5_completion_statuses_map_through_a7_only(tmp_path: Path) -> None:
    cases = (
        ("scored", 0.25, ScoreStatus.SCORED),
        ("mandatory", 1.25, ScoreStatus.MANDATORY_GATE_FAILED),
    )
    for name, gate_error, expected_status in cases:
        a7 = _a7_service(tmp_path / name)
        submission_id, envelope = _start_a7(a7)
        result = _completed_result(_pack(), gate_error=gate_error)
        assert result.status is expected_status
        outcome = CompletedFixtureRun(envelope.handle, result)

        applied = _apply_outcome(a7, outcome)

        assert type(applied) is SubmissionStatusView
        assert applied.state is SubmissionState.PUBLISHED
        card = a7.read_published(
            submission_id,
            RequesterIdentity("a8-fixture-requester-v1"),
        )
        assert card.status == expected_status.value
        assert card.eligible_for_emission is False


@pytest.mark.parametrize(
    "cause", tuple(StrategyFailureCause), ids=lambda item: item.value
)
def test_every_strategy_failure_cause_maps_at_reserved_composition_only(
    tmp_path: Path,
    cause: StrategyFailureCause,
) -> None:
    a7 = _a7_service(tmp_path / cause.value.lower())
    submission_id, envelope = _start_a7(a7)
    outcome = StrategyFailedRun(envelope.handle, cause)

    applied = _apply_outcome(a7, outcome)

    assert type(applied) is SubmissionStatusView
    assert applied.state is SubmissionState.FAILED_STRATEGY
    record = a7._store.records[submission_id.value]
    assert len(record.fee_events) == 1
    assert outcome.emission_capable is False


@pytest.mark.parametrize(
    "cause", tuple(InfrastructureCause), ids=lambda item: item.value
)
def test_every_infrastructure_cause_maps_by_retry_class_to_exact_a7_operation(
    tmp_path: Path,
    cause: InfrastructureCause,
) -> None:
    a7 = _a7_service(tmp_path / cause.value.lower(), max_attempts=2)
    submission_id, envelope = _start_a7(a7)
    policy = _policy()
    retry_class = policy.retry_class_for(cause)
    outcome = InfrastructureFailedRun(envelope.handle, retry_class, cause)

    applied = _apply_outcome(a7, outcome)

    if retry_class is InfrastructureRetryClass.RETRYABLE:
        assert type(applied) is SubmissionStatusView
        assert applied.state is SubmissionState.QUEUED
        assert (
            a7.get_status(
                submission_id,
                RequesterIdentity("a8-fixture-requester-v1"),
            ).state
            is SubmissionState.QUEUED
        )
        assert len(a7._store.records[submission_id.value].fee_events) == 1
    else:
        assert type(applied) is FeeEvent
        assert (
            a7.get_status(
                submission_id,
                RequesterIdentity("a8-fixture-requester-v1"),
            ).state
            is SubmissionState.FAILED_INFRA
        )
        assert len(a7._store.records[submission_id.value].fee_events) == 2


def test_a7_owns_retry_budget_terminalization_and_attempt_increment(
    tmp_path: Path,
) -> None:
    a7 = _a7_service(tmp_path / "retry-budget", max_attempts=2)
    submission_id, first = _start_a7(a7)
    first_outcome = InfrastructureFailedRun(
        first.handle,
        InfrastructureRetryClass.RETRYABLE,
        InfrastructureCause.EXECUTION_TIMEOUT,
    )
    queued = _apply_outcome(a7, first_outcome)
    assert type(queued) is SubmissionStatusView
    assert queued.state is SubmissionState.QUEUED

    second = a7.start_fixture_retry_attempt(
        submission_id,
        RequesterIdentity("a8-fixture-requester-v1"),
    )
    assert second.handle.attempt_number == 2
    assert second.handle.seed_pin == first.handle.seed_pin
    assert second.handle.environment_pin == first.handle.environment_pin
    terminal = _apply_outcome(
        a7,
        InfrastructureFailedRun(
            second.handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
        ),
    )
    assert type(terminal) is FeeEvent
    assert (
        a7.get_status(
            submission_id,
            RequesterIdentity("a8-fixture-requester-v1"),
        ).state
        is SubmissionState.FAILED_INFRA
    )


def test_stale_outcomes_are_rejected_by_a7_without_new_attempt_mutation(
    tmp_path: Path,
) -> None:
    a7 = _a7_service(tmp_path / "stale-outcomes", max_attempts=3)
    submission_id, first = _start_a7(a7)
    _apply_outcome(
        a7,
        InfrastructureFailedRun(
            first.handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
        ),
    )
    second = a7.start_fixture_retry_attempt(
        submission_id,
        RequesterIdentity("a8-fixture-requester-v1"),
    )
    before = _a7_snapshot(a7, submission_id)
    result = _completed_result(_pack())
    stale_outcomes = (
        CompletedFixtureRun(first.handle, result),
        StrategyFailedRun(
            first.handle,
            StrategyFailureCause.STRATEGY_RUNTIME_FAILURE,
        ),
        InfrastructureFailedRun(
            first.handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
        ),
        InfrastructureFailedRun(
            first.handle,
            InfrastructureRetryClass.NON_RETRYABLE,
            InfrastructureCause.RESOURCE_VIOLATION,
        ),
    )

    for outcome in stale_outcomes:
        with pytest.raises(SubmissionStateError):
            _apply_outcome(a7, outcome)
        assert _a7_snapshot(a7, submission_id) == before
        assert a7._store.records[submission_id.value].current_handle == second.handle


def test_no_a2_a3_or_a6_operation_is_repeated_inside_a8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import carbon.cards as cards_module
    import carbon.registry as registry_module
    import carbon.schema as schema_module

    service = _service()
    calls: list[str] = []

    def forbidden(name: str) -> Callable[..., object]:
        def fail(*args: object, **kwargs: object) -> object:
            del args, kwargs
            calls.append(name)
            raise AssertionError("upstream or publication operation was repeated")

        return fail

    monkeypatch.setattr(schema_module, "dry_validate", forbidden("a2"))
    monkeypatch.setattr(
        registry_module.ChallengeRegistry,
        "assess_live_eligibility",
        forbidden("a3-eligibility"),
    )
    monkeypatch.setattr(
        registry_module.ChallengeRegistry,
        "is_backbone_allowed",
        forbidden("a3-backbone"),
    )
    monkeypatch.setattr(
        cards_module.CardStore,
        "write_internal",
        forbidden("a6"),
    )

    assert type(service.run_fixture(_envelope())) is CompletedFixtureRun
    assert calls == []


def test_private_outcomes_have_minimum_fields_and_no_hidden_material_graph() -> None:
    outcome = _service().run_fixture(_envelope())
    assert type(outcome) is CompletedFixtureRun
    forbidden_names = {
        "context",
        "entropy",
        "private_root",
        "official_seed",
        "master_seed",
        "derived_seed",
        "domain",
        "role",
        "draw",
        "prediction",
        "reference",
        "metric",
        "score_input",
        "checkpoint",
        "model_weights",
        "exception",
        "stack",
        "path",
        "environment_variables",
        "credentials",
        "fee",
        "card",
        "diagnostic",
        "transcript",
        "receipt",
        "evidence",
        "signature",
        "emission_weights",
        "eligibility_override",
    }
    field_names = {item.name for item in fields(outcome)}
    assert forbidden_names.isdisjoint(field_names)
    assert repr(outcome) == "CompletedFixtureRun(<private>)"

    forbidden_types = (
        FixtureOfficialContext,
        FixtureOfficialEntropy,
        MockContext,
        OfficialContext,
        QualificationContext,
        DerivedSeed,
        ScoreInput,
        _FixtureBackendMaterial,
        EvaluationCard,
    )
    seen: set[int] = set()
    pending = [outcome]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if value is not outcome:
            assert not isinstance(value, forbidden_types)
        for referent in gc.get_referents(value):
            if isinstance(referent, (str, bytes, int, float, bool, type)):
                continue
            pending.append(referent)


def test_service_is_opaque_and_retains_no_run_context_or_seed_slot() -> None:
    service = _service()
    slot_names = tuple(
        (
            f"_{FixtureTrainEvalService.__name__}{slot}"
            if slot.startswith("__") and not slot.endswith("__")
            else slot
        )
        for slot in FixtureTrainEvalService.__slots__
    )
    before_slots = tuple(object.__getattribute__(service, slot) for slot in slot_names)
    service.run_fixture(_envelope())
    after_slots = tuple(object.__getattribute__(service, slot) for slot in slot_names)

    assert before_slots == after_slots
    assert repr(service) == "FixtureTrainEvalService(<fixture-only>)"
    assert {name for name in dir(service) if not name.startswith("_")} == {
        "emission_capable",
        "run_fixture",
    }
    assert not any(
        token in slot
        for slot in FixtureTrainEvalService.__slots__
        for token in ("context", "derived", "seed", "result", "material")
    )


def test_private_values_refuse_generic_copy_and_serialization() -> None:
    service = _service()
    outcome = service.run_fixture(_envelope())
    values = (
        _profile(),
        _policy(),
        _backend(),
        service,
        outcome,
        InfrastructureFailedRun(
            _handle(),
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
        ),
        StrategyFailedRun(
            _handle(),
            StrategyFailureCause.STRATEGY_RUNTIME_FAILURE,
        ),
        _valid_material(),
    )
    for value in values:
        with pytest.raises((TypeError, ValueError, AttributeError)):
            copy.copy(value)
        with pytest.raises((TypeError, ValueError, AttributeError)):
            copy.deepcopy(value)
        with pytest.raises((TypeError, ValueError, AttributeError)):
            pickle.dumps(value)
        with pytest.raises(TypeError):
            json.dumps(value)
        with pytest.raises(TypeError):
            vars(value)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        dataclasses.asdict(outcome)


def test_root_exports_are_exact_and_private_types_are_not_convenience_exports() -> None:
    assert traineval.__all__ == PUBLIC_EXPORTS
    assert {name for name in traineval.__dict__ if name in PUBLIC_EXPORTS} == set(
        PUBLIC_EXPORTS
    )
    assert not {
        "CompletedFixtureRun",
        "FixtureRunOutcome",
        "InfrastructureCause",
        "InfrastructureFailedRun",
        "InfrastructureRetryClass",
        "StrategyFailedRun",
        "StrategyFailureCause",
        "_FixtureBackendMaterial",
        "InternalResult",
        "ScoreInput",
        "FixtureOfficialContext",
        "DerivedSeed",
    }.intersection(traineval.__dict__)


def _direct_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_source_import_graph_and_calls_exclude_forbidden_owners() -> None:
    expected_imports = {
        "__init__.py": {"model", "service", "stub"},
        "model.py": {
            "__future__",
            "carbon.fees.model",
            "carbon.registry",
            "carbon.scoring.model",
            "dataclasses",
            "enum",
            "typing",
        },
        "service.py": {
            "__future__",
            "carbon.fees.model",
            "carbon.scoring",
            "carbon.scoring.model",
            "carbon.seeding",
            "math",
            "model",
            "stub",
            "typing",
        },
        "stub.py": {
            "__future__",
            "dataclasses",
            "hashlib",
            "hmac",
            "model",
            "typing",
        },
    }
    forbidden_modules = {
        "bittensor",
        "carbon.audit",
        "carbon.cards",
        "carbon.chain",
        "carbon.evaluation",
        "carbon.fees.integration",
        "carbon.fees.service",
        "carbon.fees.store",
        "carbon.leaderboard",
        "carbon.logging_utils",
        "carbon.mcp",
        "carbon.schema",
        "carbon.training",
        "carbon.validator",
        "docker",
        "jax",
        "neuralop",
        "neuraloperator",
        "numpy",
        "physicsnemo",
        "torch",
    }
    a8_paths = sorted((REPOSITORY_ROOT / "carbon/traineval").glob("*.py"))
    assert {path.name for path in a8_paths} == set(expected_imports)
    for path in a8_paths:
        imported = _direct_imports(path)
        assert imported == expected_imports[path.name], path
        assert not any(
            module == forbidden or module.startswith(forbidden + ".")
            for module in imported
            for forbidden in forbidden_modules
        ), path

    forbidden_calls = {
        "dry_validate",
        "assess_live_eligibility",
        "is_backbone_allowed",
        "is_effectively_live",
        "write_internal",
        "complete_and_publish",
        "fail_infrastructure",
        "fail_strategy",
        "retry_infrastructure",
        "hash",
        "import_module",
        "__import__",
    }
    for path in a8_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        )
        assert forbidden_calls.isdisjoint(called), path

    for path in sorted((REPOSITORY_ROOT / "carbon/fees").glob("*.py")):
        assert not any(
            module == "carbon.traineval" or module.startswith("carbon.traineval.")
            for module in _direct_imports(path)
        ), path


def test_service_source_uses_only_a5_input_factory_and_engine_for_science() -> None:
    path = REPOSITORY_ROOT / "carbon/traineval/service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_constructor_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "InternalResult" not in direct_constructor_calls
    assert "ScoreInput" not in direct_constructor_calls
    assert "_from_validated_fixture" not in attribute_calls
    assert "fixture_entropy" not in attribute_calls
    assert "fixture_score_input" in attribute_calls
    assert "score" in attribute_calls


def test_import_isolated_from_optional_heavy_and_later_modules(tmp_path: Path) -> None:
    blocked = {
        "bittensor",
        "docker",
        "jax",
        "neuralop",
        "neuraloperator",
        "numpy",
        "physicsnemo",
        "torch",
        "carbon.audit",
        "carbon.chain",
        "carbon.evaluation",
        "carbon.leaderboard",
        "carbon.logging_utils",
        "carbon.mcp",
        "carbon.training",
        "carbon.validator",
    }
    script = f"""
import importlib.abc
import json
import pathlib
import sys

blocked = {json.dumps(sorted(blocked))}

def is_blocked(fullname):
    return any(fullname == name or fullname.startswith(name + ".") for name in blocked)

class Blocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if is_blocked(fullname):
            self.attempted.append(fullname)
            raise ModuleNotFoundError("blocked A8 import", name=fullname)
        return None

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})
blocker = Blocker()
sys.meta_path.insert(0, blocker)
import carbon.traineval as traineval
loaded = sorted(name for name in sys.modules if is_blocked(name))
print(json.dumps({{
    "attempted": blocker.attempted,
    "exports": list(traineval.__all__),
    "loaded": loaded,
    "module_file": str(pathlib.Path(traineval.__file__).resolve()),
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
        "exports": list(PUBLIC_EXPORTS),
        "loaded": [],
        "module_file": str(
            (REPOSITORY_ROOT / "carbon/traineval/__init__.py").resolve()
        ),
    }


def _copy_fresh_wheel_source(destination: Path) -> None:
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


def test_fresh_no_dependency_wheel_imports_a8_outside_tree(
    tmp_path: Path,
) -> None:
    build_source = tmp_path / "fresh-source"
    wheelhouse = tmp_path / "wheelhouse"
    environment = tmp_path / "environment"
    outside = tmp_path / "outside"
    subprocess_tmp = tmp_path / "subprocess-tmp"
    for directory in (build_source, wheelhouse, outside, subprocess_tmp):
        directory.mkdir()
    _copy_fresh_wheel_source(build_source)
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

    script = textwrap.dedent(f"""
        import importlib.abc
        import importlib.metadata
        import json
        import pathlib
        import sys

        blocked = {json.dumps(sorted({
            "bittensor", "docker", "jax", "neuralop", "neuraloperator",
            "numpy", "physicsnemo", "torch", "carbon.audit", "carbon.chain",
            "carbon.evaluation", "carbon.leaderboard", "carbon.logging_utils",
            "carbon.mcp", "carbon.training", "carbon.validator",
        }))}

        def is_blocked(fullname):
            return any(
                fullname == name or fullname.startswith(name + ".")
                for name in blocked
            )

        class Blocker(importlib.abc.MetaPathFinder):
            def __init__(self):
                self.attempted = []
            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if is_blocked(fullname):
                    self.attempted.append(fullname)
                    raise ModuleNotFoundError("blocked A8 wheel import", name=fullname)
                return None

        blocker = Blocker()
        sys.meta_path.insert(0, blocker)
        import carbon.traineval as traineval
        from carbon.traineval import FixtureStubBackend, FixtureStubProfile

        profile = FixtureStubProfile()
        backend = FixtureStubBackend(
            backend_profile_id={BACKEND_PROFILE_ID!r},
            container_digest={CONTAINER_DIGEST!r},
        )
        distribution = importlib.metadata.distribution("carbon")
        loaded = sorted(name for name in sys.modules if is_blocked(name))
        print(json.dumps({{
            "attempted": blocker.attempted,
            "backend_emission": backend.emission_capable,
            "distribution": [distribution.metadata["Name"], distribution.version],
            "exports": list(traineval.__all__),
            "loaded": loaded,
            "module_file": str(pathlib.Path(traineval.__file__).resolve()),
            "profile": profile.profile_id,
        }}))
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
        "attempted": [],
        "backend_emission": False,
        "distribution": ["carbon", "0.9.0"],
        "exports": list(PUBLIC_EXPORTS),
        "loaded": [],
        "profile": "a8_fixture_stub_v1",
    }
