"""Private immutable values for the bounded A8 fixture TrainEval seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from carbon.fees.model import ExecutionAttemptHandle, ExecutionEnvironmentPin
from carbon.registry import ChallengeKey
from carbon.scoring.model import (
    InternalResult,
    ScorePackPin,
    ScoreStatus,
)

_FIXTURE_POLICY_ID = "a8_fixture_stub_policy_v1"
_FIXTURE_PROFILE_ID = "a8_fixture_stub_v1"
_FIXTURE_CHALLENGE_ID = "a5_fixture"
_FIXTURE_VERSION = "fixture-1.0"
_FIXTURE_SCORING_DIGEST = (
    "sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
)
_FIXTURE_GENERATOR_DIGEST = "sha256:" + "1" * 64
_FIXTURE_SCHEMA_VERSION = "1.0"
_FIXTURE_NUMERICAL_PROFILE = "python_binary64_v1"
_FIXTURE_NUMERIC_INPUT_KEYS = (
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
_FIXTURE_BOOLEAN_INPUT_KEYS = ("finite_ok",)


class FixtureRunRequestError(ValueError):
    """Stable non-echoing failure for an invalid fixture request."""

    def __init__(self) -> None:
        self.code = "traineval.fixture_request_invalid"
        super().__init__("Fixture execution request is invalid.")


class FixtureRunIdentityError(ValueError):
    """Stable non-echoing failure for contradictory fixture identity."""

    def __init__(self) -> None:
        self.code = "traineval.fixture_identity_invalid"
        super().__init__("Fixture execution identity is invalid.")


class InfrastructureRetryClass(str, Enum):
    """Trusted fixture-policy classification, never retry permission."""

    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"


class StrategyFailureCause(str, Enum):
    """Closed positive-attribution causes reserved for a future real backend."""

    STRATEGY_RUNTIME_FAILURE = "STRATEGY_RUNTIME_FAILURE"
    STRATEGY_TRAINING_FAILURE = "STRATEGY_TRAINING_FAILURE"
    STRATEGY_NUMERICAL_FAILURE = "STRATEGY_NUMERICAL_FAILURE"


class InfrastructureCause(str, Enum):
    """Closed operational causes produced by trusted TrainEval integration."""

    CONFIGURATION_UNAVAILABLE = "CONFIGURATION_UNAVAILABLE"
    SCORE_PACK_MISMATCH = "SCORE_PACK_MISMATCH"
    SCORE_PACK_NOT_READY = "SCORE_PACK_NOT_READY"
    CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"
    ENVIRONMENT_MISMATCH = "ENVIRONMENT_MISMATCH"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    BACKEND_STARTUP_FAILURE = "BACKEND_STARTUP_FAILURE"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    RESOURCE_VIOLATION = "RESOURCE_VIOLATION"
    BACKEND_NUMERICAL_FAILURE = "BACKEND_NUMERICAL_FAILURE"
    REFERENCE_FAILURE = "REFERENCE_FAILURE"
    INCOMPLETE_EXECUTION_MATERIAL = "INCOMPLETE_EXECUTION_MATERIAL"
    SCORE_INPUT_FAILURE = "SCORE_INPUT_FAILURE"
    SCORE_COMPUTATION_FAILURE = "SCORE_COMPUTATION_FAILURE"


class _NonSerializableValue:
    __slots__ = ()

    def __getstate__(self) -> object:
        raise TypeError(f"{type(self).__name__} does not support serialization")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(f"{type(self).__name__} does not support serialization")

    def __copy__(self) -> object:
        raise TypeError(f"{type(self).__name__} does not support generic copying")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(f"{type(self).__name__} does not support generic copying")


def _require_exact_uninitialized(
    value: object,
    expected_type: type[object],
    slot_name: str,
) -> None:
    """Reject subclasses and supported-API constructor re-entry."""
    if type(value) is not expected_type:
        raise FixtureRunRequestError()
    try:
        object.__getattribute__(value, slot_name)
    except AttributeError:
        return
    raise FixtureRunRequestError()


def _is_canonical_enum_member(value: object, enum_type: type[Enum]) -> bool:
    return type(value) is enum_type and any(value is member for member in enum_type)


def _owned_challenge_key(value: object) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise FixtureRunIdentityError()
    try:
        return ChallengeKey(value.challenge_id, value.version)
    except Exception:  # noqa: BLE001 - do not render hostile identity values.
        raise FixtureRunIdentityError() from None


def _owned_score_pack_pin(value: object) -> ScorePackPin:
    if type(value) is not ScorePackPin:
        raise FixtureRunIdentityError()
    try:
        challenge_key = _owned_challenge_key(value.challenge_key)
        return ScorePackPin(
            challenge_key=challenge_key,
            scoring_version=value.scoring_version,
            scoring_digest=value.scoring_digest,
            generator_version_required=value.generator_version_required,
            generator_digest_required=value.generator_digest_required,
            schema_version=value.schema_version,
            numerical_profile=value.numerical_profile,
            fixture_origin=value.fixture_origin,
        )
    except FixtureRunIdentityError:
        raise
    except Exception:  # noqa: BLE001 - do not render hostile identity values.
        raise FixtureRunIdentityError() from None


def _owned_attempt_handle(value: object) -> ExecutionAttemptHandle:
    if type(value) is not ExecutionAttemptHandle:
        raise FixtureRunIdentityError()
    try:
        return ExecutionAttemptHandle(
            submission_id=value.submission_id,
            attempt_number=value.attempt_number,
            admission_kind=value.admission_kind,
            seed_pin=value.seed_pin,
            environment_pin=value.environment_pin,
        )
    except Exception:  # noqa: BLE001 - do not render hostile identity values.
        raise FixtureRunIdentityError() from None


def _owned_environment_pin(value: object) -> ExecutionEnvironmentPin:
    if type(value) is not ExecutionEnvironmentPin:
        raise FixtureRunIdentityError()
    try:
        return ExecutionEnvironmentPin(
            backend_profile_id=value.backend_profile_id,
            container_digest=value.container_digest,
        )
    except Exception:  # noqa: BLE001 - do not render hostile identity values.
        raise FixtureRunIdentityError() from None


def _validated_environment_identity(
    backend_profile_id: object,
    container_digest: object,
) -> ExecutionEnvironmentPin:
    try:
        return ExecutionEnvironmentPin(
            backend_profile_id=backend_profile_id,  # type: ignore[arg-type]
            container_digest=container_digest,  # type: ignore[arg-type]
        )
    except Exception:  # noqa: BLE001 - configuration errors are non-echoing.
        raise FixtureRunIdentityError() from None


def _owned_internal_result(value: object) -> InternalResult:
    """Delegate recursive result ownership and validation to A5."""
    if type(value) is not InternalResult:
        raise FixtureRunRequestError()
    try:
        owned = value._copy()
    except Exception:  # noqa: BLE001 - never render a hostile result graph.
        raise FixtureRunRequestError() from None
    if type(owned) is not InternalResult or owned is value:
        raise FixtureRunRequestError()
    return owned


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureStubProfile(_NonSerializableValue):
    """The sole conspicuous, non-scientific A8 fixture profile."""

    profile_id: str = field(default=_FIXTURE_PROFILE_ID, init=False)
    challenge_key: ChallengeKey = field(init=False)
    scoring_version: str = field(default=_FIXTURE_VERSION, init=False)
    scoring_digest: str = field(default=_FIXTURE_SCORING_DIGEST, init=False)
    generator_version_required: str = field(default=_FIXTURE_VERSION, init=False)
    generator_digest_required: str = field(
        default=_FIXTURE_GENERATOR_DIGEST,
        init=False,
    )
    schema_version: str = field(default=_FIXTURE_SCHEMA_VERSION, init=False)
    numerical_profile: str = field(
        default=_FIXTURE_NUMERICAL_PROFILE,
        init=False,
    )
    fixture_origin: bool = field(default=True, init=False)
    numeric_input_keys: tuple[str, ...] = field(
        default=_FIXTURE_NUMERIC_INPUT_KEYS,
        init=False,
    )
    boolean_input_keys: tuple[str, ...] = field(
        default=_FIXTURE_BOOLEAN_INPUT_KEYS,
        init=False,
    )

    def __init__(self) -> None:
        _require_exact_uninitialized(self, FixtureStubProfile, "profile_id")
        object.__setattr__(self, "profile_id", _FIXTURE_PROFILE_ID)
        object.__setattr__(
            self,
            "challenge_key",
            ChallengeKey(_FIXTURE_CHALLENGE_ID, _FIXTURE_VERSION),
        )
        object.__setattr__(self, "scoring_version", _FIXTURE_VERSION)
        object.__setattr__(self, "scoring_digest", _FIXTURE_SCORING_DIGEST)
        object.__setattr__(self, "generator_version_required", _FIXTURE_VERSION)
        object.__setattr__(
            self,
            "generator_digest_required",
            _FIXTURE_GENERATOR_DIGEST,
        )
        object.__setattr__(self, "schema_version", _FIXTURE_SCHEMA_VERSION)
        object.__setattr__(self, "numerical_profile", _FIXTURE_NUMERICAL_PROFILE)
        object.__setattr__(self, "fixture_origin", True)
        object.__setattr__(self, "numeric_input_keys", _FIXTURE_NUMERIC_INPUT_KEYS)
        object.__setattr__(self, "boolean_input_keys", _FIXTURE_BOOLEAN_INPUT_KEYS)

    def __repr__(self) -> str:
        return "FixtureStubProfile(<fixture-only>)"

    def score_pack_pin(self) -> ScorePackPin:
        """Return a fresh exact A5 fixture pin for trusted composition."""
        if not _is_supported_profile(self):
            raise FixtureRunRequestError()
        return ScorePackPin(
            challenge_key=ChallengeKey(
                self.challenge_key.challenge_id,
                self.challenge_key.version,
            ),
            scoring_version=self.scoring_version,
            scoring_digest=self.scoring_digest,
            generator_version_required=self.generator_version_required,
            generator_digest_required=self.generator_digest_required,
            schema_version=self.schema_version,
            numerical_profile=self.numerical_profile,
            fixture_origin=self.fixture_origin,
        )


def _is_supported_profile(value: object) -> bool:
    if type(value) is not FixtureStubProfile:
        return False
    try:
        challenge_key = _owned_challenge_key(value.challenge_key)
        return (
            type(value.profile_id) is str
            and value.profile_id == _FIXTURE_PROFILE_ID
            and challenge_key == ChallengeKey(_FIXTURE_CHALLENGE_ID, _FIXTURE_VERSION)
            and type(value.scoring_version) is str
            and value.scoring_version == _FIXTURE_VERSION
            and type(value.scoring_digest) is str
            and value.scoring_digest == _FIXTURE_SCORING_DIGEST
            and type(value.generator_version_required) is str
            and value.generator_version_required == _FIXTURE_VERSION
            and type(value.generator_digest_required) is str
            and value.generator_digest_required == _FIXTURE_GENERATOR_DIGEST
            and type(value.schema_version) is str
            and value.schema_version == _FIXTURE_SCHEMA_VERSION
            and type(value.numerical_profile) is str
            and value.numerical_profile == _FIXTURE_NUMERICAL_PROFILE
            and type(value.fixture_origin) is bool
            and value.fixture_origin is True
            and type(value.numeric_input_keys) is tuple
            and value.numeric_input_keys == _FIXTURE_NUMERIC_INPUT_KEYS
            and all(type(item) is str for item in value.numeric_input_keys)
            and type(value.boolean_input_keys) is tuple
            and value.boolean_input_keys == _FIXTURE_BOOLEAN_INPUT_KEYS
            and all(type(item) is str for item in value.boolean_input_keys)
        )
    except Exception:  # noqa: BLE001 - trusted configuration fails closed.
        return False


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureRuntimePolicy(_NonSerializableValue):
    """Exact fixture test policy; it supplies classification, not retry authority."""

    policy_id: str = field(default=_FIXTURE_POLICY_ID, init=False)
    backend_profile_id: str
    container_digest: str
    cause_retry_classes: tuple[
        tuple[InfrastructureCause, InfrastructureRetryClass], ...
    ]

    def __init__(
        self,
        *,
        backend_profile_id: str,
        container_digest: str,
        cause_retry_classes: tuple[
            tuple[InfrastructureCause, InfrastructureRetryClass], ...
        ],
    ) -> None:
        _require_exact_uninitialized(self, FixtureRuntimePolicy, "policy_id")
        environment = _validated_environment_identity(
            backend_profile_id,
            container_digest,
        )
        if type(cause_retry_classes) is not tuple:
            raise FixtureRunRequestError()
        supplied: dict[InfrastructureCause, InfrastructureRetryClass] = {}
        for item in cause_retry_classes:
            if (
                type(item) is not tuple
                or len(item) != 2
                or not _is_canonical_enum_member(item[0], InfrastructureCause)
                or not _is_canonical_enum_member(
                    item[1],
                    InfrastructureRetryClass,
                )
                or item[0] in supplied
            ):
                raise FixtureRunRequestError()
            supplied[item[0]] = item[1]
        if set(supplied) != set(InfrastructureCause):
            raise FixtureRunRequestError()
        owned_mapping = tuple((cause, supplied[cause]) for cause in InfrastructureCause)
        object.__setattr__(self, "policy_id", _FIXTURE_POLICY_ID)
        object.__setattr__(
            self,
            "backend_profile_id",
            environment.backend_profile_id,
        )
        object.__setattr__(self, "container_digest", environment.container_digest)
        object.__setattr__(self, "cause_retry_classes", owned_mapping)

    def __repr__(self) -> str:
        return "FixtureRuntimePolicy(<fixture-only>)"

    def execution_environment_pin(self) -> ExecutionEnvironmentPin:
        """Reconstruct safe identity; this is not executable configuration."""
        if not _is_supported_policy(self):
            raise FixtureRunRequestError()
        return _validated_environment_identity(
            self.backend_profile_id,
            self.container_digest,
        )

    def retry_class_for(
        self,
        cause: InfrastructureCause,
    ) -> InfrastructureRetryClass:
        """Return the exact injected class with no fallback."""
        if not _is_supported_policy(self) or not _is_canonical_enum_member(
            cause,
            InfrastructureCause,
        ):
            raise FixtureRunRequestError()
        for configured_cause, retry_class in self.cause_retry_classes:
            if configured_cause is cause:
                return retry_class
        raise FixtureRunRequestError()


def _is_supported_policy(value: object) -> bool:
    if type(value) is not FixtureRuntimePolicy:
        return False
    try:
        if (
            type(value.policy_id) is not str
            or value.policy_id != _FIXTURE_POLICY_ID
            or type(value.backend_profile_id) is not str
            or type(value.container_digest) is not str
            or type(value.cause_retry_classes) is not tuple
            or len(value.cause_retry_classes) != len(InfrastructureCause)
        ):
            return False
        _validated_environment_identity(
            value.backend_profile_id,
            value.container_digest,
        )
        observed: list[InfrastructureCause] = []
        for item in value.cause_retry_classes:
            if (
                type(item) is not tuple
                or len(item) != 2
                or not _is_canonical_enum_member(item[0], InfrastructureCause)
                or not _is_canonical_enum_member(
                    item[1],
                    InfrastructureRetryClass,
                )
                or any(item[0] is cause for cause in observed)
            ):
                return False
            observed.append(item[0])
        return all(
            observed[index] is cause for index, cause in enumerate(InfrastructureCause)
        )
    except Exception:  # noqa: BLE001 - trusted configuration fails closed.
        return False


@dataclass(frozen=True, slots=True, repr=False)
class CompletedFixtureRun(_NonSerializableValue):
    """Private trusted completion carrying one exact owned A5 result."""

    handle: ExecutionAttemptHandle
    internal_result: InternalResult
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if type(self) is not CompletedFixtureRun:
            raise FixtureRunRequestError()
        handle = _owned_attempt_handle(self.handle)
        result = _owned_internal_result(self.internal_result)
        if (
            result.status is not ScoreStatus.SCORED
            and result.status is not ScoreStatus.MANDATORY_GATE_FAILED
        ):
            raise FixtureRunRequestError()
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "internal_result", result)

    def __repr__(self) -> str:
        return "CompletedFixtureRun(<private>)"


@dataclass(frozen=True, slots=True, repr=False)
class StrategyFailedRun(_NonSerializableValue):
    """Private positive-attribution result reserved for a future real backend."""

    handle: ExecutionAttemptHandle
    cause: StrategyFailureCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if type(self) is not StrategyFailedRun:
            raise FixtureRunRequestError()
        handle = _owned_attempt_handle(self.handle)
        if not _is_canonical_enum_member(self.cause, StrategyFailureCause):
            raise FixtureRunRequestError()
        object.__setattr__(self, "handle", handle)

    def __repr__(self) -> str:
        return "StrategyFailedRun(<private>)"


@dataclass(frozen=True, slots=True, repr=False)
class InfrastructureFailedRun(_NonSerializableValue):
    """Private operational result carrying only closed classification."""

    handle: ExecutionAttemptHandle
    retry_class: InfrastructureRetryClass
    cause: InfrastructureCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if type(self) is not InfrastructureFailedRun:
            raise FixtureRunRequestError()
        handle = _owned_attempt_handle(self.handle)
        if not _is_canonical_enum_member(
            self.retry_class,
            InfrastructureRetryClass,
        ) or not _is_canonical_enum_member(self.cause, InfrastructureCause):
            raise FixtureRunRequestError()
        object.__setattr__(self, "handle", handle)

    def __repr__(self) -> str:
        return "InfrastructureFailedRun(<private>)"


FixtureRunOutcome = CompletedFixtureRun | StrategyFailedRun | InfrastructureFailedRun


__all__ = (
    "CompletedFixtureRun",
    "FixtureRunIdentityError",
    "FixtureRunOutcome",
    "FixtureRunRequestError",
    "FixtureRuntimePolicy",
    "FixtureStubProfile",
    "InfrastructureCause",
    "InfrastructureFailedRun",
    "InfrastructureRetryClass",
    "StrategyFailedRun",
    "StrategyFailureCause",
)
