"""Fixture-only A8 orchestration over exact A4, A5, and A7 boundaries."""

from __future__ import annotations

import math
from typing import ClassVar

from carbon.fees.model import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FixtureExecutionEnvelope,
    StrategyHash,
)
from carbon.scoring import (
    BooleanInput,
    LoadedScorePack,
    NumericInput,
    ScoreEngine,
    ScoreInput,
    ScoreInputError,
    ScorePackError,
)
from carbon.scoring.model import ScoreStatus
from carbon.seeding import (
    DerivedSeed,
    DeterministicFixtureProvider,
    FixtureOfficialContext,
    RoleKey,
    SeedDomain,
    SeedPin,
    acquire_fixture_official_context,
    derive_fixture_official_seed,
)

from .model import (
    CompletedFixtureRun,
    FixtureRunIdentityError,
    FixtureRunOutcome,
    FixtureRunRequestError,
    FixtureRuntimePolicy,
    FixtureStubProfile,
    InfrastructureCause,
    InfrastructureFailedRun,
    _is_supported_policy,
    _is_supported_profile,
    _owned_attempt_handle,
    _owned_challenge_key,
    _owned_environment_pin,
    _owned_internal_result,
    _owned_score_pack_pin,
    _require_exact_uninitialized,
)
from .stub import FixtureStubBackend, _FixtureBackendMaterial

_TRAIN_ROLE = "a8_fixture_train"
_EVAL_ROLE = "a8_fixture_eval"
_STRESS_ROLE = "a8_fixture_stress"


def _pin_matches_handle(pack_pin: object, seed_pin: object) -> bool:
    if type(seed_pin) is not SeedPin:
        return False
    try:
        return (
            pack_pin.challenge_key == seed_pin.challenge_key
            and pack_pin.scoring_version == seed_pin.scoring_version
            and pack_pin.scoring_digest == seed_pin.scoring_digest
            and pack_pin.generator_version_required == seed_pin.generator_version
            and pack_pin.generator_digest_required == seed_pin.generator_digest
        )
    except Exception:  # noqa: BLE001 - trusted identity mismatch fails closed.
        return False


def _validated_material(
    material: object,
    profile: FixtureStubProfile,
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, bool], ...]] | None:
    if type(material) is not _FixtureBackendMaterial:
        return None
    try:
        numeric_values = material.numeric_values
        boolean_values = material.boolean_values
    except Exception:  # noqa: BLE001 - never render hostile backend output.
        return None
    if type(numeric_values) is not tuple or type(boolean_values) is not tuple:
        return None
    if len(numeric_values) != len(profile.numeric_input_keys) or len(
        boolean_values
    ) != len(profile.boolean_input_keys):
        return None

    owned_numeric: list[tuple[str, float]] = []
    for entry, expected_key in zip(numeric_values, profile.numeric_input_keys):
        if type(entry) is not tuple or len(entry) != 2:
            return None
        key, value = entry
        if (
            type(key) is not str
            or key != expected_key
            or type(value) is not float
            or not math.isfinite(value)
            or value < 0.0
        ):
            return None
        owned_numeric.append((key, value))

    owned_boolean: list[tuple[str, bool]] = []
    for entry, expected_key in zip(boolean_values, profile.boolean_input_keys):
        if type(entry) is not tuple or len(entry) != 2:
            return None
        key, value = entry
        if type(key) is not str or key != expected_key or type(value) is not bool:
            return None
        if key == "finite_ok" and value is not True:
            return None
        owned_boolean.append((key, value))
    return tuple(owned_numeric), tuple(owned_boolean)


def _is_exact_factory_score_input(
    value: object,
    expected_pin: object,
    numeric_inputs: tuple[NumericInput, ...],
    boolean_inputs: tuple[BooleanInput, ...],
) -> bool:
    """Validate only A5's factory handoff; ScoreEngine remains authoritative."""
    if type(value) is not ScoreInput:
        return False
    try:
        owned_pin = _owned_score_pack_pin(value.pack_pin)
        observed_numeric = value.numeric_inputs
        observed_boolean = value.boolean_inputs
        if (
            owned_pin != expected_pin
            or type(observed_numeric) is not tuple
            or type(observed_boolean) is not tuple
            or len(observed_numeric) != len(numeric_inputs)
            or len(observed_boolean) != len(boolean_inputs)
        ):
            return False
        for observed, expected in zip(
            observed_numeric,
            numeric_inputs,
            strict=True,
        ):
            if (
                type(observed) is not NumericInput
                or type(observed.key) is not str
                or type(observed.value) is not float
                or observed.key != expected.key
                or observed.value != expected.value
            ):
                return False
        for observed, expected in zip(
            observed_boolean,
            boolean_inputs,
            strict=True,
        ):
            if (
                type(observed) is not BooleanInput
                or type(observed.key) is not str
                or type(observed.value) is not bool
                or observed.key != expected.key
                or observed.value is not expected.value
            ):
                return False
        return True
    except Exception:  # noqa: BLE001 - malformed A5 handoffs are non-echoing.
        return False


def _preflight_score_pack(pack: LoadedScorePack) -> None:
    """Use A5's engine validator without inventing another pack validator."""
    try:
        pack_ready = pack.ready
    except Exception:  # noqa: BLE001 - preflight failures are non-echoing.
        raise FixtureRunRequestError() from None
    if type(pack_ready) is not bool:
        raise FixtureRunRequestError()
    try:
        result = ScoreEngine.score(None, pack)
    except ScoreInputError as exc:
        try:
            is_required = (
                type(exc) is ScoreInputError
                and type(exc.code) is str
                and exc.code == "score_input.required"
            )
        except Exception:  # noqa: BLE001 - malformed errors are non-echoing.
            raise FixtureRunRequestError() from None
        if pack_ready is True and is_required:
            return
        raise FixtureRunRequestError() from None
    except ScorePackError:
        raise FixtureRunRequestError() from None
    except Exception:  # noqa: BLE001 - preflight failures are non-echoing.
        raise FixtureRunRequestError() from None
    if pack_ready is True:
        raise FixtureRunRequestError() from None
    try:
        owned_result = _owned_internal_result(result)
        expected_pin = _owned_score_pack_pin(pack.pack_pin)
    except Exception:  # noqa: BLE001 - malformed results are non-echoing.
        raise FixtureRunRequestError() from None
    if (
        owned_result.status is not ScoreStatus.PACK_NOT_READY
        or owned_result.pack_pin != expected_pin
    ):
        raise FixtureRunRequestError()


class FixtureTrainEvalService:
    """Trusted synchronous fixture service; this is not a sandbox."""

    __slots__ = (
        "__backend",
        "__declared_environment",
        "__policy",
        "__profile",
        "__provider",
        "__score_pack",
    )

    emission_capable: ClassVar[bool] = False

    def __init__(
        self,
        *,
        profile: FixtureStubProfile,
        provider: DeterministicFixtureProvider,
        score_pack: LoadedScorePack,
        policy: FixtureRuntimePolicy,
        declared_environment: ExecutionEnvironmentPin,
        backend: FixtureStubBackend,
    ) -> None:
        _require_exact_uninitialized(
            self,
            FixtureTrainEvalService,
            "_FixtureTrainEvalService__profile",
        )
        if (
            type(profile) is not FixtureStubProfile
            or type(provider) is not DeterministicFixtureProvider
            or type(score_pack) is not LoadedScorePack
            or type(policy) is not FixtureRuntimePolicy
            or type(declared_environment) is not ExecutionEnvironmentPin
            or type(backend) is not FixtureStubBackend
        ):
            raise FixtureRunRequestError()
        if not _is_supported_profile(profile) or not _is_supported_policy(policy):
            raise FixtureRunRequestError()

        try:
            owned_profile = FixtureStubProfile()
            loaded_pin = _owned_score_pack_pin(score_pack.pack_pin)
            if loaded_pin != owned_profile.score_pack_pin():
                raise FixtureRunIdentityError()
            owned_policy = FixtureRuntimePolicy(
                backend_profile_id=policy.backend_profile_id,
                container_digest=policy.container_digest,
                cause_retry_classes=policy.cause_retry_classes,
            )
            policy_environment = owned_policy.execution_environment_pin()
            owned_declared_environment = _owned_environment_pin(declared_environment)
            owned_backend = FixtureStubBackend(
                backend_profile_id=backend.backend_profile_id,
                container_digest=backend.container_digest,
            )
            backend_environment = owned_backend._environment_pin()
        except FixtureRunRequestError:
            raise FixtureRunRequestError() from None
        except FixtureRunIdentityError:
            raise FixtureRunIdentityError() from None
        except Exception:  # noqa: BLE001 - trusted configuration fails closed.
            raise FixtureRunRequestError() from None

        if (
            policy_environment != owned_declared_environment
            or type(backend_environment) is not ExecutionEnvironmentPin
            or backend_environment != owned_declared_environment
            or owned_backend.emission_capable is not False
            or self.emission_capable is not False
        ):
            raise FixtureRunIdentityError()

        _preflight_score_pack(score_pack)

        object.__setattr__(self, "_FixtureTrainEvalService__profile", owned_profile)
        object.__setattr__(self, "_FixtureTrainEvalService__provider", provider)
        object.__setattr__(self, "_FixtureTrainEvalService__score_pack", score_pack)
        object.__setattr__(self, "_FixtureTrainEvalService__policy", owned_policy)
        object.__setattr__(
            self,
            "_FixtureTrainEvalService__declared_environment",
            owned_declared_environment,
        )
        object.__setattr__(self, "_FixtureTrainEvalService__backend", owned_backend)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("FixtureTrainEvalService is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("FixtureTrainEvalService is immutable")

    def __repr__(self) -> str:
        return "FixtureTrainEvalService(<fixture-only>)"

    def __getstate__(self) -> object:
        raise TypeError("FixtureTrainEvalService does not support serialization")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("FixtureTrainEvalService does not support serialization")

    def __copy__(self) -> object:
        raise TypeError("FixtureTrainEvalService does not support generic copying")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("FixtureTrainEvalService does not support generic copying")

    def _infrastructure(
        self,
        handle: ExecutionAttemptHandle,
        cause: InfrastructureCause,
    ) -> InfrastructureFailedRun:
        return InfrastructureFailedRun(
            handle=handle,
            retry_class=self.__policy.retry_class_for(cause),
            cause=cause,
        )

    def run_fixture(self, envelope: FixtureExecutionEnvelope) -> FixtureRunOutcome:
        """Execute the exact fixture envelope without interpreting Strategy."""
        if type(envelope) is not FixtureExecutionEnvelope:
            raise FixtureRunRequestError()
        try:
            handle = _owned_attempt_handle(envelope.handle)
        except Exception:  # noqa: BLE001 - boundary values are never rendered.
            raise FixtureRunIdentityError() from None
        if handle.admission_kind is not AdmissionKind.FIXTURE:
            raise FixtureRunRequestError()
        try:
            challenge_key = _owned_challenge_key(envelope.challenge_key)
            if type(envelope.strategy) is not dict:
                raise FixtureRunIdentityError()
            if type(envelope.strategy_hash) is not StrategyHash:
                raise FixtureRunIdentityError()
            StrategyHash(envelope.strategy_hash.value)
        except Exception:  # noqa: BLE001 - boundary values are never rendered.
            raise FixtureRunIdentityError() from None
        if challenge_key != handle.seed_pin.challenge_key:
            raise FixtureRunIdentityError()

        try:
            loaded_pin = _owned_score_pack_pin(self.__score_pack.pack_pin)
            profile_pin = self.__profile.score_pack_pin()
        except Exception:  # noqa: BLE001 - trusted configuration is non-echoing.
            return self._infrastructure(
                handle,
                InfrastructureCause.CONFIGURATION_UNAVAILABLE,
            )
        if loaded_pin != profile_pin or not _pin_matches_handle(
            loaded_pin,
            handle.seed_pin,
        ):
            return self._infrastructure(
                handle,
                InfrastructureCause.SCORE_PACK_MISMATCH,
            )
        if handle.environment_pin != self.__declared_environment:
            return self._infrastructure(
                handle,
                InfrastructureCause.ENVIRONMENT_MISMATCH,
            )

        try:
            pack_ready = self.__score_pack.ready
        except Exception:  # noqa: BLE001 - trusted configuration is non-echoing.
            return self._infrastructure(
                handle,
                InfrastructureCause.CONFIGURATION_UNAVAILABLE,
            )
        if pack_ready is not True:
            try:
                unready = ScoreEngine.score(None, self.__score_pack)
                owned_unready = _owned_internal_result(unready)
                is_pack_not_ready = (
                    owned_unready.status is ScoreStatus.PACK_NOT_READY
                    and owned_unready.pack_pin == loaded_pin
                )
            except Exception:  # noqa: BLE001 - A5 exception text is never returned.
                return self._infrastructure(
                    handle,
                    InfrastructureCause.SCORE_COMPUTATION_FAILURE,
                )
            if is_pack_not_ready:
                return self._infrastructure(
                    handle,
                    InfrastructureCause.SCORE_PACK_NOT_READY,
                )
            return self._infrastructure(
                handle,
                InfrastructureCause.SCORE_COMPUTATION_FAILURE,
            )

        try:
            context = acquire_fixture_official_context(
                self.__provider,
                handle.seed_pin,
            )
            if (
                type(context) is not FixtureOfficialContext
                or type(context.pin) is not SeedPin
                or context.pin != handle.seed_pin
            ):
                raise FixtureRunIdentityError()
            train_derived = derive_fixture_official_seed(
                context,
                SeedDomain.OFFICIAL_TRAIN,
                RoleKey(_TRAIN_ROLE),
                0,
            )
            eval_derived = derive_fixture_official_seed(
                context,
                SeedDomain.OFFICIAL_EVAL,
                RoleKey(_EVAL_ROLE),
                0,
            )
            stress_derived = derive_fixture_official_seed(
                context,
                SeedDomain.OFFICIAL_STRESS,
                RoleKey(_STRESS_ROLE),
                0,
            )
            if (
                type(train_derived) is not DerivedSeed
                or type(eval_derived) is not DerivedSeed
                or type(stress_derived) is not DerivedSeed
            ):
                raise FixtureRunIdentityError()
            train_seed = train_derived.as_backend_bytes()
            eval_seed = eval_derived.as_backend_bytes()
            stress_seed = stress_derived.as_backend_bytes()
            del train_derived, eval_derived, stress_derived
        except Exception:  # noqa: BLE001 - context failures are never rendered.
            return self._infrastructure(
                handle,
                InfrastructureCause.CONTEXT_UNAVAILABLE,
            )

        try:
            material = self.__backend._execute_fixture(
                profile=self.__profile,
                train_seed=train_seed,
                eval_seed=eval_seed,
                stress_seed=stress_seed,
            )
        except Exception:  # noqa: BLE001 - hostile backend exceptions are redacted.
            return self._infrastructure(
                handle,
                InfrastructureCause.BACKEND_UNAVAILABLE,
            )
        finally:
            del context, train_seed, eval_seed, stress_seed

        validated = _validated_material(material, self.__profile)
        del material
        if validated is None:
            return self._infrastructure(
                handle,
                InfrastructureCause.INCOMPLETE_EXECUTION_MATERIAL,
            )
        numeric_values, boolean_values = validated
        try:
            numeric_inputs = tuple(
                NumericInput(key, value) for key, value in numeric_values
            )
            boolean_inputs = tuple(
                BooleanInput(key, value) for key, value in boolean_values
            )
            score_input = self.__score_pack.fixture_score_input(
                numeric_inputs=numeric_inputs,
                boolean_inputs=boolean_inputs,
            )
            if not _is_exact_factory_score_input(
                score_input,
                loaded_pin,
                numeric_inputs,
                boolean_inputs,
            ):
                raise FixtureRunIdentityError()
        except Exception:  # noqa: BLE001 - A5 input failures are redacted.
            return self._infrastructure(
                handle,
                InfrastructureCause.SCORE_INPUT_FAILURE,
            )
        finally:
            del numeric_values, boolean_values

        try:
            result = ScoreEngine.score(score_input, self.__score_pack)
        except Exception:  # noqa: BLE001 - A5 computation failures are redacted.
            return self._infrastructure(
                handle,
                InfrastructureCause.SCORE_COMPUTATION_FAILURE,
            )
        finally:
            del score_input, numeric_inputs, boolean_inputs

        try:
            owned_result = _owned_internal_result(result)
            result_pin = _owned_score_pack_pin(owned_result.pack_pin)
            if result_pin != loaded_pin:
                raise FixtureRunIdentityError()
            if owned_result.status is ScoreStatus.PACK_NOT_READY:
                return self._infrastructure(
                    handle,
                    InfrastructureCause.SCORE_PACK_NOT_READY,
                )
            if (
                owned_result.status is not ScoreStatus.SCORED
                and owned_result.status is not ScoreStatus.MANDATORY_GATE_FAILED
            ) or owned_result.eligible_for_emission is not False:
                raise FixtureRunIdentityError()
            return CompletedFixtureRun(handle=handle, internal_result=owned_result)
        except Exception:  # noqa: BLE001 - result graph failures are redacted.
            return self._infrastructure(
                handle,
                InfrastructureCause.SCORE_COMPUTATION_FAILURE,
            )


__all__ = ("FixtureTrainEvalService",)
