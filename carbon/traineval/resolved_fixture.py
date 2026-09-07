"""B-07F fixture-only consumer for exact B-02B resolved construction plans."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, TypeAlias

from carbon.construction import (
    BoundTrainingLever,
    CandidateAssemblyContract,
    CandidateAssemblyContractRef,
    CompileAccepted,
    CompileIssue,
    CompileRejected,
    CompilerIdentity,
    ConsumerTarget,
    ParameterCatalog,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    ResolvedTrainingSamplingPolicy,
    SelectedSurface,
    SurfaceValueType,
    TrainingLeverKind,
    TrainingSamplingPolicyRef,
    compile_strategy,
)
from carbon.evaluation.refs import FixtureReferenceAssetRef
from carbon.fees.model import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FixtureExecutionEnvelope,
    StrategyHash,
)
from carbon.fees.strategy_identity import SubmissionResourceLimits
from carbon.generators.refs import BurgersFixtureConfigurationRef
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    ClassBundle,
    ResearchResourcePolicy,
    ResearchResourcePolicyRef,
    ResourceClass,
    ResourceClassRef,
    StaticAssessmentOutcome,
    assess_static_resources,
    research_resource_policy_to_ref,
    static_resource_assessment_to_ref,
    validate_research_resource_policy_bundle,
)
from carbon.scoring import BooleanInput, LoadedScorePack, NumericInput, ScoreEngine
from carbon.scoring.model import InternalResult, ScorePackPin, ScoreStatus
from carbon.seeding import (
    DerivedSeed,
    DeterministicFixtureProvider,
    FixtureOfficialContext,
    RoleKey,
    SeedDomain,
    acquire_fixture_official_context,
    derive_fixture_official_seed,
)
from carbon.toy import (
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_TRAINING_OBSERVATIONS,
    construct_fixture_model,
    evaluate_fixture_reference,
)

from .model import (
    CompletedFixtureRun,
    FixtureRunIdentityError,
    FixtureRunRequestError,
    FixtureRuntimePolicy,
    InfrastructureCause,
    InfrastructureFailedRun,
    _owned_attempt_handle,
    _owned_internal_result,
)
from .service import (
    _is_exact_factory_score_input,
    _pin_matches_handle,
    _preflight_score_pack,
)

_TRAIN_ROLE = RoleKey("fixture_training_role_key")
_AUTHORITY = "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
_LEVER_SURFACE = "fixture_sampling_level"
_LEVER_CONSUMER = ConsumerTarget("fixture_training", "sampling_level")
_MAX_INPUT_KEYS = 64
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)


class FixtureConstructionCause(str, Enum):
    """Closed candidate-construction failures, never scientific outcomes."""

    PLAN_IDENTITY_MISMATCH = "PLAN_IDENTITY_MISMATCH"
    LEVER_BINDING_INVALID = "LEVER_BINDING_INVALID"
    LEVER_VALUE_UNSUPPORTED = "LEVER_VALUE_UNSUPPORTED"
    REGISTERED_LEVER_IGNORED = "REGISTERED_LEVER_IGNORED"
    TOY_FIT_INVALID = "TOY_FIT_INVALID"


class FixtureResourceCause(str, Enum):
    """Closed B-02C failure projection."""

    POLICY_NOT_ADMISSIBLE = "POLICY_NOT_ADMISSIBLE"
    POLICY_EVALUATION_FAILED = "POLICY_EVALUATION_FAILED"


class FixtureReferenceCause(str, Enum):
    """Closed fixture-reference failure projection."""

    ASSET_IDENTITY_MISMATCH = "ASSET_IDENTITY_MISMATCH"
    REFERENCE_EVALUATION_FAILED = "REFERENCE_EVALUATION_FAILED"


class FixtureMeasurementCause(str, Enum):
    """Closed fixture-measurement failure projection."""

    MEASUREMENT_INPUT_FAILED = "MEASUREMENT_INPUT_FAILED"
    SCORE_COMPUTATION_FAILED = "SCORE_COMPUTATION_FAILED"
    RESULT_IDENTITY_MISMATCH = "RESULT_IDENTITY_MISMATCH"


class _PrivateFixtureValue:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<private>)"

    def __getstate__(self) -> object:
        raise TypeError(f"{type(self).__name__} does not support serialization")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(f"{type(self).__name__} does not support serialization")


def _exact_enum(value: object, enum_type: type[Enum]) -> bool:
    return type(value) is enum_type and any(value is item for item in enum_type)


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _is_digest(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _challenge_value(value: ChallengeKey) -> list[str]:
    return [value.challenge_id, value.version]


def _ref_value(value: object) -> dict[str, object]:
    """Project exact validated refs without invoking protected repr/serialization."""
    challenge = value.challenge_key  # type: ignore[attr-defined]
    projected: dict[str, object] = {
        "challenge": _challenge_value(challenge),
        "content_digest": value.content_digest,  # type: ignore[attr-defined]
        "type": type(value).__name__,
    }
    for name in (
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
    ):
        if hasattr(value, name):
            projected[name] = getattr(value, name)
    return projected


def _score_pin_value(pin: ScorePackPin) -> dict[str, object]:
    return {
        "challenge": _challenge_value(pin.challenge_key),
        "fixture_origin": pin.fixture_origin,
        "generator_digest": pin.generator_digest_required,
        "generator_version": pin.generator_version_required,
        "numerical_profile": pin.numerical_profile,
        "schema_version": pin.schema_version,
        "scoring_digest": pin.scoring_digest,
        "scoring_version": pin.scoring_version,
    }


def _result_digest(result: InternalResult) -> str:
    return _digest(
        _json_bytes(
            {
                "combined_score": result.combined_score,
                "gates": [
                    [item.gate_id, item.passed, item.mandatory]
                    for item in result.gate_decisions
                ],
                "legs": [
                    [
                        leg.leg,
                        [[item.identifier, item.score] for item in leg.components],
                        leg.score,
                    ]
                    for leg in result.leg_scores
                ],
                "pack": _score_pin_value(result.pack_pin),
                "status": result.status.value,
            }
        )
    )


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureToyAsset(_PrivateFixtureValue):
    """Exact fixed toy asset; values cannot be supplied by a run caller."""

    challenge_key: ChallengeKey
    generator_configuration_ref: BurgersFixtureConfigurationRef
    reference_asset_ref: FixtureReferenceAssetRef
    measurement_contract_ref: MeasurementContractRef
    training_observations: tuple[tuple[int, int], ...] = field(init=False)
    heldout_observations: tuple[tuple[int, int], ...] = field(init=False)
    authority_marker: str = field(default=_AUTHORITY, init=False)

    def __init__(
        self,
        *,
        challenge_key: ChallengeKey,
        generator_configuration_ref: BurgersFixtureConfigurationRef,
        reference_asset_ref: FixtureReferenceAssetRef,
        measurement_contract_ref: MeasurementContractRef,
    ) -> None:
        if (
            type(challenge_key) is not ChallengeKey
            or type(generator_configuration_ref) is not BurgersFixtureConfigurationRef
            or type(reference_asset_ref) is not FixtureReferenceAssetRef
            or type(measurement_contract_ref) is not MeasurementContractRef
            or any(
                ref.challenge_key != challenge_key
                for ref in (
                    generator_configuration_ref,
                    reference_asset_ref,
                    measurement_contract_ref,
                )
            )
        ):
            raise FixtureRunRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            ChallengeKey(challenge_key.challenge_id, challenge_key.version),
        )
        object.__setattr__(
            self, "generator_configuration_ref", generator_configuration_ref
        )
        object.__setattr__(self, "reference_asset_ref", reference_asset_ref)
        object.__setattr__(self, "measurement_contract_ref", measurement_contract_ref)
        object.__setattr__(self, "training_observations", FIXTURE_TRAINING_OBSERVATIONS)
        object.__setattr__(self, "heldout_observations", FIXTURE_HELDOUT_OBSERVATIONS)
        object.__setattr__(self, "authority_marker", _AUTHORITY)

    def content_digest(self) -> str:
        return _digest(
            _json_bytes(
                {
                    "authority": self.authority_marker,
                    "challenge": _challenge_value(self.challenge_key),
                    "generator": _ref_value(self.generator_configuration_ref),
                    "heldout": self.heldout_observations,
                    "measurement": _ref_value(self.measurement_contract_ref),
                    "reference": _ref_value(self.reference_asset_ref),
                    "training": self.training_observations,
                }
            )
        )


@dataclass(frozen=True, slots=True, repr=False)
class FixtureCompilationFailed(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    issues: tuple[CompileIssue, ...]
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))
        if (
            type(self.issues) is not tuple
            or not self.issues
            or any(type(item) is not CompileIssue for item in self.issues)
        ):
            raise FixtureRunRequestError()


@dataclass(frozen=True, slots=True, repr=False)
class FixtureConstructionFailed(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    cause: FixtureConstructionCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))
        if not _exact_enum(self.cause, FixtureConstructionCause):
            raise FixtureRunRequestError()


@dataclass(frozen=True, slots=True, repr=False)
class FixtureResourceFailed(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    cause: FixtureResourceCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))
        if not _exact_enum(self.cause, FixtureResourceCause):
            raise FixtureRunRequestError()


@dataclass(frozen=True, slots=True, repr=False)
class FixtureReferenceFailed(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    cause: FixtureReferenceCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))
        if not _exact_enum(self.cause, FixtureReferenceCause):
            raise FixtureRunRequestError()


@dataclass(frozen=True, slots=True, repr=False)
class FixtureMeasurementFailed(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    cause: FixtureMeasurementCause
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))
        if not _exact_enum(self.cause, FixtureMeasurementCause):
            raise FixtureRunRequestError()


@dataclass(frozen=True, slots=True, repr=False)
class FixtureReconstructionReceipt(_PrivateFixtureValue):
    handle: ExecutionAttemptHandle
    strategy_hash: StrategyHash
    construction_plan_ref: ResolvedConstructionPlanRef
    training_policy_ref: TrainingSamplingPolicyRef
    candidate_assembly_ref: CandidateAssemblyContractRef
    parameter_catalog_ref: ParameterCatalogRef
    training_support_digest: str
    compiler_implementation_digest: str
    resource_policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    static_assessment_digest: str
    execution_environment: ExecutionEnvironmentPin
    generator_configuration_ref: BurgersFixtureConfigurationRef
    reference_asset_ref: FixtureReferenceAssetRef
    measurement_contract_ref: MeasurementContractRef
    fixture_asset_digest: str
    consumed_surface_id: str
    consumed_value: int
    constructed_artifact_digest: str
    authority_marker: str = field(default=_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        challenge = self.handle.seed_pin.challenge_key
        if (
            type(self.handle) is not ExecutionAttemptHandle
            or type(self.strategy_hash) is not StrategyHash
            or type(self.construction_plan_ref) is not ResolvedConstructionPlanRef
            or type(self.training_policy_ref) is not TrainingSamplingPolicyRef
            or type(self.candidate_assembly_ref) is not CandidateAssemblyContractRef
            or type(self.parameter_catalog_ref) is not ParameterCatalogRef
            or type(self.resource_policy_ref) is not ResearchResourcePolicyRef
            or type(self.resource_class_ref) is not ResourceClassRef
            or type(self.execution_environment) is not ExecutionEnvironmentPin
            or type(self.generator_configuration_ref)
            is not BurgersFixtureConfigurationRef
            or type(self.reference_asset_ref) is not FixtureReferenceAssetRef
            or type(self.measurement_contract_ref) is not MeasurementContractRef
            or type(self.consumed_surface_id) is not str
            or self.consumed_surface_id != _LEVER_SURFACE
            or type(self.consumed_value) is not int
            or self.consumed_value not in (1, 2)
            or self.handle.admission_kind is not AdmissionKind.FIXTURE
            or self.execution_environment != self.handle.environment_pin
            or any(
                ref.challenge_key != challenge
                for ref in (
                    self.construction_plan_ref,
                    self.training_policy_ref,
                    self.candidate_assembly_ref,
                    self.parameter_catalog_ref,
                    self.resource_policy_ref,
                    self.resource_class_ref,
                    self.generator_configuration_ref,
                    self.reference_asset_ref,
                    self.measurement_contract_ref,
                )
            )
            or any(
                not _is_digest(value)
                for value in (
                    self.training_support_digest,
                    self.compiler_implementation_digest,
                    self.static_assessment_digest,
                    self.fixture_asset_digest,
                    self.constructed_artifact_digest,
                )
            )
        ):
            raise FixtureRunRequestError()
        object.__setattr__(self, "handle", _owned_attempt_handle(self.handle))

    def canonical_bytes(self) -> bytes:
        handle = self.handle
        pin = handle.seed_pin
        binding_digest = _digest(pin.evaluation_binding._copy_bytes())
        return _json_bytes(
            {
                "assembly": _ref_value(self.candidate_assembly_ref),
                "assessment_digest": self.static_assessment_digest,
                "attempt": [handle.submission_id.value, handle.attempt_number],
                "authority": self.authority_marker,
                "catalog": _ref_value(self.parameter_catalog_ref),
                "compiler_digest": self.compiler_implementation_digest,
                "constructed_artifact_digest": self.constructed_artifact_digest,
                "environment": [
                    self.execution_environment.backend_profile_id,
                    self.execution_environment.container_digest,
                ],
                "fixture_asset_digest": self.fixture_asset_digest,
                "generator": _ref_value(self.generator_configuration_ref),
                "measurement": _ref_value(self.measurement_contract_ref),
                "plan": _ref_value(self.construction_plan_ref),
                "reference": _ref_value(self.reference_asset_ref),
                "resource_class": _ref_value(self.resource_class_ref),
                "resource_policy": _ref_value(self.resource_policy_ref),
                "seed_pin_digest": _digest(
                    _json_bytes(
                        {
                            "binding": binding_digest,
                            "challenge": _challenge_value(pin.challenge_key),
                            "generator": [pin.generator_version, pin.generator_digest],
                            "scoring": [pin.scoring_version, pin.scoring_digest],
                            "scheme": pin.seed_scheme,
                        }
                    )
                ),
                "strategy_hash": self.strategy_hash.value,
                "surface": [self.consumed_surface_id, self.consumed_value],
                "training_policy": _ref_value(self.training_policy_ref),
                "training_support_digest": self.training_support_digest,
            }
        )

    @property
    def receipt_ref(self) -> str:
        return _digest(self.canonical_bytes())


@dataclass(frozen=True, slots=True, repr=False)
class FixtureResultReceipt(_PrivateFixtureValue):
    reconstruction_receipt_ref: str
    score_pack_pin: ScorePackPin
    result_status: ScoreStatus
    result_digest: str
    authority_marker: str = field(default=_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        if (
            not _is_digest(self.reconstruction_receipt_ref)
            or type(self.score_pack_pin) is not ScorePackPin
            or not _exact_enum(self.result_status, ScoreStatus)
            or self.result_status
            not in (ScoreStatus.SCORED, ScoreStatus.MANDATORY_GATE_FAILED)
            or not _is_digest(self.result_digest)
        ):
            raise FixtureRunRequestError()

    def canonical_bytes(self) -> bytes:
        return _json_bytes(
            {
                "authority": self.authority_marker,
                "reconstruction_receipt_ref": self.reconstruction_receipt_ref,
                "result_digest": self.result_digest,
                "result_status": self.result_status.value,
                "score_pack": _score_pin_value(self.score_pack_pin),
            }
        )

    @property
    def receipt_ref(self) -> str:
        return _digest(self.canonical_bytes())


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedFixtureCompletedRun(_PrivateFixtureValue):
    completed_run: CompletedFixtureRun
    construction_plan_ref: ResolvedConstructionPlanRef
    reconstruction_receipt: FixtureReconstructionReceipt
    result_receipt: FixtureResultReceipt
    emission_capable: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if (
            type(self.completed_run) is not CompletedFixtureRun
            or type(self.construction_plan_ref) is not ResolvedConstructionPlanRef
            or type(self.reconstruction_receipt) is not FixtureReconstructionReceipt
            or type(self.result_receipt) is not FixtureResultReceipt
            or self.result_receipt.reconstruction_receipt_ref
            != self.reconstruction_receipt.receipt_ref
            or self.construction_plan_ref
            != self.reconstruction_receipt.construction_plan_ref
            or self.completed_run.handle != self.reconstruction_receipt.handle
            or self.completed_run.internal_result.pack_pin
            != self.result_receipt.score_pack_pin
            or self.completed_run.internal_result.status
            != self.result_receipt.result_status
            or _result_digest(self.completed_run.internal_result)
            != self.result_receipt.result_digest
        ):
            raise FixtureRunRequestError()


ResolvedFixtureRunOutcome: TypeAlias = (
    ResolvedFixtureCompletedRun
    | FixtureCompilationFailed
    | FixtureConstructionFailed
    | FixtureResourceFailed
    | FixtureReferenceFailed
    | FixtureMeasurementFailed
    | InfrastructureFailedRun
)


def _construct_fixture_model(
    observations: tuple[tuple[int, int], ...], level: int, seed: bytes
) -> tuple[float, str]:
    """Compatibility seam delegating to the shared fixture semantic owner."""

    return construct_fixture_model(observations, level, seed)


def _evaluate_fixture_reference(
    coefficient: float, observations: tuple[tuple[int, int], ...]
) -> float:
    """Compatibility seam delegating to the shared fixture semantic owner."""

    return evaluate_fixture_reference(coefficient, observations)


class ResolvedPlanFixtureTrainEvalService:
    """Trusted fixture provider; exact-type checks are not a production sandbox."""

    __slots__ = (
        "__assembly",
        "__assembly_ref",
        "__authoring_artifacts",
        "__authoring_origin",
        "__boolean_input_keys",
        "__catalog",
        "__catalog_ref",
        "__challenge",
        "__class_bundle",
        "__compiler",
        "__declared_environment",
        "__expected_class_ref",
        "__expected_policy_ref",
        "__fixture_asset",
        "__lever_semantics_ref",
        "__numeric_input_keys",
        "__policy",
        "__policy_ref",
        "__provider",
        "__resource_class",
        "__resource_class_ref",
        "__runtime_policy",
        "__score_pack",
        "__strategy_limits",
    )
    emission_capable: ClassVar[bool] = False

    def __init__(
        self,
        *,
        challenge_key: ChallengeKey,
        candidate_assembly: CandidateAssemblyContract,
        candidate_assembly_ref: CandidateAssemblyContractRef,
        parameter_catalog: ParameterCatalog,
        parameter_catalog_ref: ParameterCatalogRef,
        authoring_origin: object,
        authoring_artifacts: tuple[object, ...],
        compiler_identity: CompilerIdentity,
        strategy_limits: SubmissionResourceLimits,
        resource_policy: ResearchResourcePolicy,
        resource_policy_ref: ResearchResourcePolicyRef,
        class_bundle: ClassBundle,
        selected_resource_class: ResourceClass,
        selected_resource_class_ref: ResourceClassRef,
        expected_active_policy_ref: ResearchResourcePolicyRef,
        expected_active_resource_class_ref: ResourceClassRef,
        provider: DeterministicFixtureProvider,
        score_pack: LoadedScorePack,
        runtime_policy: FixtureRuntimePolicy,
        declared_environment: ExecutionEnvironmentPin,
        fixture_asset: FixtureToyAsset,
        lever_executable_semantics_ref: object,
        numeric_input_keys: tuple[str, ...],
        boolean_input_keys: tuple[str, ...],
    ) -> None:
        exact = (
            type(challenge_key) is ChallengeKey
            and type(candidate_assembly) is CandidateAssemblyContract
            and type(candidate_assembly_ref) is CandidateAssemblyContractRef
            and type(parameter_catalog) is ParameterCatalog
            and type(parameter_catalog_ref) is ParameterCatalogRef
            and type(authoring_artifacts) is tuple
            and type(compiler_identity) is CompilerIdentity
            and type(strategy_limits) is SubmissionResourceLimits
            and type(resource_policy) is ResearchResourcePolicy
            and type(resource_policy_ref) is ResearchResourcePolicyRef
            and type(class_bundle) is tuple
            and type(selected_resource_class) is ResourceClass
            and type(selected_resource_class_ref) is ResourceClassRef
            and type(expected_active_policy_ref) is ResearchResourcePolicyRef
            and type(expected_active_resource_class_ref) is ResourceClassRef
            and type(provider) is DeterministicFixtureProvider
            and type(score_pack) is LoadedScorePack
            and type(runtime_policy) is FixtureRuntimePolicy
            and type(declared_environment) is ExecutionEnvironmentPin
            and type(fixture_asset) is FixtureToyAsset
            and type(numeric_input_keys) is tuple
            and type(boolean_input_keys) is tuple
        )
        if (
            not exact
            or not numeric_input_keys
            or len(numeric_input_keys) > _MAX_INPUT_KEYS
            or len(boolean_input_keys) > _MAX_INPUT_KEYS
        ):
            raise FixtureRunRequestError()
        try:
            if (
                candidate_assembly.to_ref() != candidate_assembly_ref
                or parameter_catalog.to_ref(candidate_assembly=candidate_assembly)
                != parameter_catalog_ref
                or resource_policy_ref != expected_active_policy_ref
                or selected_resource_class_ref != expected_active_resource_class_ref
                or research_resource_policy_to_ref(
                    resource_policy,
                    class_bundle=validate_research_resource_policy_bundle(
                        resource_policy, class_bundle=class_bundle
                    ),
                )
                != resource_policy_ref
                or (selected_resource_class, selected_resource_class_ref)
                not in class_bundle
                or fixture_asset.challenge_key != challenge_key
                or score_pack.pack_pin.challenge_key != challenge_key
                or score_pack.pack_pin.generator_digest_required
                != fixture_asset.generator_configuration_ref.content_digest
                or resource_policy.challenge_key != challenge_key
                or runtime_policy.execution_environment_pin() != declared_environment
                or any(
                    type(key) is not str
                    for key in (*numeric_input_keys, *boolean_input_keys)
                )
                or len({*numeric_input_keys, *boolean_input_keys})
                != len(numeric_input_keys) + len(boolean_input_keys)
            ):
                raise FixtureRunIdentityError()
            binding = next(
                entry
                for entry in parameter_catalog.entries
                if entry.surface_id == _LEVER_SURFACE
            ).training_lever_binding
            if (
                type(binding) is not BoundTrainingLever
                or binding.kind is not TrainingLeverKind.SAMPLING
                or binding.executable_semantics_ref != lever_executable_semantics_ref
                or next(
                    entry
                    for entry in parameter_catalog.entries
                    if entry.surface_id == _LEVER_SURFACE
                ).consumer_target
                != _LEVER_CONSUMER
            ):
                raise FixtureRunIdentityError()
            _preflight_score_pack(score_pack)
        except (FixtureRunIdentityError, FixtureRunRequestError):
            raise
        except Exception:  # noqa: BLE001 - trusted configuration fails closed.
            raise FixtureRunRequestError() from None
        for name, value in {
            "assembly": candidate_assembly,
            "assembly_ref": candidate_assembly_ref,
            "authoring_artifacts": authoring_artifacts,
            "authoring_origin": authoring_origin,
            "catalog": parameter_catalog,
            "catalog_ref": parameter_catalog_ref,
            "challenge": challenge_key,
            "class_bundle": class_bundle,
            "compiler": compiler_identity,
            "declared_environment": declared_environment,
            "expected_class_ref": expected_active_resource_class_ref,
            "expected_policy_ref": expected_active_policy_ref,
            "fixture_asset": fixture_asset,
            "policy": resource_policy,
            "policy_ref": resource_policy_ref,
            "provider": provider,
            "resource_class": selected_resource_class,
            "resource_class_ref": selected_resource_class_ref,
            "runtime_policy": runtime_policy,
            "score_pack": score_pack,
            "strategy_limits": strategy_limits,
            "numeric_input_keys": numeric_input_keys,
            "boolean_input_keys": boolean_input_keys,
            "lever_semantics_ref": lever_executable_semantics_ref,
        }.items():
            object.__setattr__(
                self, f"_ResolvedPlanFixtureTrainEvalService__{name}", value
            )

    def __repr__(self) -> str:
        return "ResolvedPlanFixtureTrainEvalService(<fixture-only>)"

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ResolvedPlanFixtureTrainEvalService is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("ResolvedPlanFixtureTrainEvalService is immutable")

    def __getstate__(self) -> object:
        raise TypeError(
            "ResolvedPlanFixtureTrainEvalService does not support serialization"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(
            "ResolvedPlanFixtureTrainEvalService does not support serialization"
        )

    def __copy__(self) -> object:
        raise TypeError("ResolvedPlanFixtureTrainEvalService does not support copying")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("ResolvedPlanFixtureTrainEvalService does not support copying")

    def _infrastructure(
        self, handle: ExecutionAttemptHandle, cause: InfrastructureCause
    ) -> InfrastructureFailedRun:
        return InfrastructureFailedRun(
            handle, self.__runtime_policy.retry_class_for(cause), cause
        )

    def run_fixture(
        self, envelope: FixtureExecutionEnvelope
    ) -> ResolvedFixtureRunOutcome:
        if type(envelope) is not FixtureExecutionEnvelope:
            raise FixtureRunRequestError()
        try:
            handle = _owned_attempt_handle(envelope.handle)
            if (
                handle.admission_kind is not AdmissionKind.FIXTURE
                or envelope.challenge_key != self.__challenge
                or handle.seed_pin.challenge_key != self.__challenge
                or type(envelope.strategy_hash) is not StrategyHash
            ):
                raise FixtureRunIdentityError()
        except Exception:  # noqa: BLE001 - hostile boundary values stay redacted.
            raise FixtureRunIdentityError() from None

        compiled = compile_strategy(
            envelope.strategy,
            challenge_key=self.__challenge,
            candidate_assembly=self.__assembly,
            candidate_assembly_ref=self.__assembly_ref,
            parameter_catalog=self.__catalog,
            parameter_catalog_ref=self.__catalog_ref,
            authoring_origin=self.__authoring_origin,
            authoring_artifacts=self.__authoring_artifacts,
            compiler_identity=self.__compiler,
            strategy_limits=self.__strategy_limits,
        )
        if type(compiled) is CompileRejected:
            return FixtureCompilationFailed(handle, compiled.issues)
        if type(compiled) is not CompileAccepted:
            return FixtureCompilationFailed(
                handle,
                (
                    CompileIssue(
                        "compile.internal_failure", "/", "Compilation failed closed."
                    ),
                ),
            )
        plan = compiled.construction_plan
        policy = compiled.training_policy
        if (
            plan.strategy_hash != envelope.strategy_hash
            or plan.challenge_key != self.__challenge
            or plan.candidate_assembly_ref != self.__assembly_ref
            or plan.parameter_catalog_ref != self.__catalog_ref
            or plan.compiler_identity != self.__compiler
            or plan.training_support_ref != self.__assembly.training_support_ref
            or plan.training_sampling_policy_ref != compiled.training_policy_ref
        ):
            return FixtureConstructionFailed(
                handle, FixtureConstructionCause.PLAN_IDENTITY_MISMATCH
            )

        level: int | None = None
        try:
            if (
                type(policy) is not ResolvedTrainingSamplingPolicy
                or len(policy.bindings) != 1
            ):
                raise LookupError
            binding = policy.bindings[0]
            surface = next(
                item
                for item in plan.resolved_surfaces
                if item.surface_id == _LEVER_SURFACE
            )
            if (
                binding.surface_id != _LEVER_SURFACE
                or binding.kind is not TrainingLeverKind.SAMPLING
                or binding.executable_semantics_ref != self.__lever_semantics_ref
                or type(surface) is not SelectedSurface
                or surface.consumer_target != _LEVER_CONSUMER
                or surface.value != binding.resolved_value
                or binding.resolved_value.value_type is not SurfaceValueType.UINT64
            ):
                raise LookupError
            value = binding.resolved_value.value
            if type(value) is not int or value not in (1, 2):
                return FixtureConstructionFailed(
                    handle, FixtureConstructionCause.LEVER_VALUE_UNSUPPORTED
                )
            level = value
        except Exception:  # noqa: BLE001 - malformed plan graphs stay redacted.
            return FixtureConstructionFailed(
                handle, FixtureConstructionCause.REGISTERED_LEVER_IGNORED
            )

        if handle.environment_pin != self.__declared_environment:
            return self._infrastructure(
                handle, InfrastructureCause.ENVIRONMENT_MISMATCH
            )
        if not _pin_matches_handle(self.__score_pack.pack_pin, handle.seed_pin):
            return self._infrastructure(handle, InfrastructureCause.SCORE_PACK_MISMATCH)

        try:
            assessment = assess_static_resources(
                plan=plan,
                plan_ref=compiled.construction_plan_ref,
                policy=self.__policy,
                policy_ref=self.__policy_ref,
                class_bundle=self.__class_bundle,
                selected_class=self.__resource_class,
                selected_class_ref=self.__resource_class_ref,
                expected_active_policy_ref=self.__expected_policy_ref,
                expected_active_resource_class_ref=self.__expected_class_ref,
                authority_context=self.__policy.authority_context,
            )
        except Exception:  # noqa: BLE001 - B-02C internals stay in their domain.
            return FixtureResourceFailed(
                handle, FixtureResourceCause.POLICY_EVALUATION_FAILED
            )
        if assessment.outcome is not StaticAssessmentOutcome.ADMISSIBLE:
            return FixtureResourceFailed(
                handle, FixtureResourceCause.POLICY_NOT_ADMISSIBLE
            )
        assessment_ref = static_resource_assessment_to_ref(assessment)

        if self.__fixture_asset.challenge_key != self.__challenge:
            return FixtureReferenceFailed(
                handle, FixtureReferenceCause.ASSET_IDENTITY_MISMATCH
            )
        try:
            context = acquire_fixture_official_context(self.__provider, handle.seed_pin)
            if (
                type(context) is not FixtureOfficialContext
                or context.pin != handle.seed_pin
            ):
                raise FixtureRunIdentityError()
            train_seed_value = derive_fixture_official_seed(
                context, SeedDomain.OFFICIAL_TRAIN, _TRAIN_ROLE, 0
            )
            if type(train_seed_value) is not DerivedSeed:
                raise FixtureRunIdentityError()
            train_seed = train_seed_value.as_backend_bytes()
        except Exception:  # noqa: BLE001 - entropy/provider failures are redacted.
            return self._infrastructure(handle, InfrastructureCause.CONTEXT_UNAVAILABLE)
        finally:
            context = None

        try:
            coefficient, artifact_digest = _construct_fixture_model(
                self.__fixture_asset.training_observations, level, train_seed
            )
        except Exception:  # noqa: BLE001 - construction failures are classified.
            return FixtureConstructionFailed(
                handle, FixtureConstructionCause.TOY_FIT_INVALID
            )
        finally:
            train_seed = b""
        try:
            heldout_error = _evaluate_fixture_reference(
                coefficient, self.__fixture_asset.heldout_observations
            )
        except Exception:  # noqa: BLE001 - reference failures are classified.
            return FixtureReferenceFailed(
                handle, FixtureReferenceCause.REFERENCE_EVALUATION_FAILED
            )
        try:
            measured_error = heldout_error / (1.0 + heldout_error)
            numeric = tuple(
                NumericInput(key, measured_error) for key in self.__numeric_input_keys
            )
            boolean = tuple(
                BooleanInput(key, True) for key in self.__boolean_input_keys
            )
            score_input = self.__score_pack.fixture_score_input(
                numeric_inputs=numeric, boolean_inputs=boolean
            )
            if not _is_exact_factory_score_input(
                score_input, self.__score_pack.pack_pin, numeric, boolean
            ):
                raise FixtureRunIdentityError()
        except Exception:  # noqa: BLE001 - measurement inputs stay private.
            return FixtureMeasurementFailed(
                handle, FixtureMeasurementCause.MEASUREMENT_INPUT_FAILED
            )
        try:
            result = ScoreEngine.score(score_input, self.__score_pack)
            owned_result = _owned_internal_result(result)
        except Exception:  # noqa: BLE001 - scorer internals stay private.
            return FixtureMeasurementFailed(
                handle, FixtureMeasurementCause.SCORE_COMPUTATION_FAILED
            )
        if (
            owned_result.status
            not in (ScoreStatus.SCORED, ScoreStatus.MANDATORY_GATE_FAILED)
            or owned_result.eligible_for_emission is not False
            or not _pin_matches_handle(owned_result.pack_pin, handle.seed_pin)
        ):
            return FixtureMeasurementFailed(
                handle, FixtureMeasurementCause.RESULT_IDENTITY_MISMATCH
            )
        completed = CompletedFixtureRun(handle, owned_result)
        reconstruction = FixtureReconstructionReceipt(
            handle,
            envelope.strategy_hash,
            compiled.construction_plan_ref,
            compiled.training_policy_ref,
            self.__assembly_ref,
            self.__catalog_ref,
            plan.training_support_ref.content_digest,
            self.__compiler.implementation_digest,
            self.__policy_ref,
            self.__resource_class_ref,
            assessment_ref.content_digest,
            self.__declared_environment,
            self.__fixture_asset.generator_configuration_ref,
            self.__fixture_asset.reference_asset_ref,
            self.__fixture_asset.measurement_contract_ref,
            self.__fixture_asset.content_digest(),
            _LEVER_SURFACE,
            level,
            artifact_digest,
        )
        result_receipt = FixtureResultReceipt(
            reconstruction.receipt_ref,
            owned_result.pack_pin,
            owned_result.status,
            _result_digest(owned_result),
        )
        return ResolvedFixtureCompletedRun(
            completed,
            compiled.construction_plan_ref,
            reconstruction,
            result_receipt,
        )


__all__ = (
    "FixtureCompilationFailed",
    "FixtureConstructionCause",
    "FixtureConstructionFailed",
    "FixtureMeasurementCause",
    "FixtureMeasurementFailed",
    "FixtureReconstructionReceipt",
    "FixtureReferenceCause",
    "FixtureReferenceFailed",
    "FixtureResourceCause",
    "FixtureResourceFailed",
    "FixtureResultReceipt",
    "FixtureToyAsset",
    "ResolvedFixtureCompletedRun",
    "ResolvedFixtureRunOutcome",
    "ResolvedPlanFixtureTrainEvalService",
)
