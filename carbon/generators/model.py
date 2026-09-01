"""Core immutable values for the deterministic B-03 generator runtime."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
from typing import TypeVar

from carbon.authoring.canonical import encode_value, top_level_ref_to_canonical
from carbon.authoring.cases import RelatedPopulationBinding
from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import EvidenceScopeBinding
from carbon.authoring.loading import LoadedAuthoringArtifact, OriginTag
from carbon.authoring.model import (
    ApplicabilityBinding,
    ApplicabilityTag,
    DisclosureClass,
    DisclosureContract,
    SamplingRole,
)
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_finite_float64,
    validate_int64,
    validate_tagged_sha256,
    validate_uint64,
    validate_version_token,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    is_owner_ref,
    is_top_level_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import RoleKey, SeedDomain

from .errors import GeneratorInputCode, GeneratorValidationError
from .refs import (
    BurgersFixtureConfigurationRef,
    GeneratorEnvironmentRef,
    GeneratorFailureOccurrenceRef,
    GeneratorFailureReasonRef,
    GeneratorReplayCommitmentRef,
    GeneratorRequestRef,
    GeneratorResultRef,
    GeneratorRuntimeRef,
    IntendedUnitLinkDecisionRef,
    PendingGenerationAttemptRef,
    is_generator_ref,
    reconstruct_generator_ref,
)

T = TypeVar("T")


def _invalid(path: str, code: GeneratorInputCode = GeneratorInputCode.INVALID_VALUE):
    return GeneratorValidationError(code, path=path)


def _exact(value: object, expected: type[T], path: str) -> T:
    if type(value) is not expected:
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    return value


def _validate_challenge_scoped_graph(
    value: object,
    challenge_key: ChallengeKey,
    *,
    path: str,
    seen: set[int] | None = None,
) -> None:
    """Reject any nested B-02A/B-03 identity ref outside one Challenge."""

    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)

    if is_owner_ref(value):
        ref = require_owner_ref(value, value.ref_kind)
        scope = ref.scope_binding
        if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
            raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
        return
    if is_top_level_ref(value) or is_generator_ref(value):
        if value.challenge_key != challenge_key:
            raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
        return
    if type(value) is tuple:
        for index, item in enumerate(value):
            _validate_challenge_scoped_graph(
                item,
                challenge_key,
                path=f"{path}/{index}",
                seen=seen,
            )
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _validate_challenge_scoped_graph(
                getattr(value, field.name),
                challenge_key,
                path=f"{path}/{field.name}",
                seen=seen,
            )


def _exact_enum(value: object, expected: type[T], path: str) -> T:
    return _exact(value, expected, path)


def _exact_tuple(
    value: object,
    expected: type[T] | tuple[type[object], ...] | None,
    path: str,
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> tuple[T, ...]:
    if type(value) is not tuple:
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(path)
    if expected is not None:
        allowed = expected if type(expected) is tuple else (expected,)
        if any(type(item) not in allowed for item in value):
            raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    copied = tuple(value)
    if unique and len(set(copied)) != len(copied):
        raise _invalid(path)
    return copied


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path, GeneratorInputCode.WRONG_TYPE)


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _digest(value: object, path: str) -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _uint64(value: object, path: str) -> int:
    try:
        return validate_uint64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _int64(value: object, path: str) -> int:
    try:
        return validate_int64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _finite_float64(value: object, path: str) -> float:
    try:
        result = validate_finite_float64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        result = None
    if result is None:
        raise _invalid(path)
    if not math.isfinite(result):
        raise _invalid(path)
    return result


def _owner(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey | None = None,
) -> object:
    try:
        result = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        result = None
    if result is None:
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    if challenge_key is not None:
        scope = object.__getattribute__(result, "scope_binding")
        if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
            raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
    return result


def _owner_tuple(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey | None = None,
    nonempty: bool = False,
) -> tuple[object, ...]:
    copied = _exact_tuple(value, None, path, nonempty=nonempty)
    result = tuple(
        _owner(item, kind, path, challenge_key=challenge_key) for item in copied
    )
    if len(set(result)) != len(result):
        raise _invalid(path)
    return result


def _reconstruct_applicability_owner(
    value: object,
    bound_kind: str,
    path: str,
) -> ApplicabilityBinding[object]:
    binding = _exact(value, ApplicabilityBinding, path)
    tag = _exact_enum(binding.tag, ApplicabilityTag, f"{path}/tag")
    checked = _owner(
        binding.value,
        bound_kind if tag is ApplicabilityTag.BOUND else "applicability_reason",
        f"{path}/value",
    )
    return ApplicabilityBinding(tag, checked)


def _reconstruct_applicability_top(
    value: object,
    expected: type[T],
    path: str,
) -> ApplicabilityBinding[T]:
    binding = _exact(value, ApplicabilityBinding, path)
    tag = _exact_enum(binding.tag, ApplicabilityTag, f"{path}/tag")
    if tag is ApplicabilityTag.BOUND:
        checked = _exact(
            _reconstruct_any_top_ref(binding.value, f"{path}/value"),
            expected,
            f"{path}/value",
        )
        return ApplicabilityBinding.bound(checked)
    return ApplicabilityBinding.not_applicable(
        _owner(
            binding.value,
            "applicability_reason",
            f"{path}/value",
        )
    )


def _reconstruct_disclosure_contract(
    value: object,
    path: str,
) -> DisclosureContract:
    contract = _exact(value, DisclosureContract, path)
    validation_failure: tuple[str, str] | None = None
    try:
        reconstructed = DisclosureContract(
            contract.public_field_ids,
            contract.internal_field_ids,
            contract.protected_field_ids,
            _owner(
                contract.aggregation_policy_ref,
                "aggregation_policy",
                f"{path}/aggregation_policy_ref",
            ),
            _owner(
                contract.release_policy_ref,
                "release_policy",
                f"{path}/release_policy_ref",
            ),
        )
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
        reconstructed = None
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
        reconstructed = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstructed is None:
        raise _invalid(path)
    return reconstructed


def _reconstruct_evidence_scope(
    value: object,
    path: str,
) -> EvidenceScopeBinding:
    scope = _exact(value, EvidenceScopeBinding, path)
    campaign = _reconstruct_applicability_owner(
        scope.evidence_campaign_binding,
        "evidence_campaign",
        f"{path}/evidence_campaign_binding",
    )
    query = _reconstruct_applicability_top(
        scope.query_population_binding,
        InstanceDistributionContractRef,
        f"{path}/query_population_binding",
    )
    observation = _reconstruct_applicability_top(
        scope.observation_population_binding,
        InstanceDistributionContractRef,
        f"{path}/observation_population_binding",
    )
    intended = _owner(
        scope.intended_estimand_or_reporting_ref,
        "intended_estimand_or_reporting",
        f"{path}/intended_estimand_or_reporting_ref",
    )
    measurement = _reconstruct_applicability_owner(
        scope.measurement_applicability_binding,
        "measurement_applicability",
        f"{path}/measurement_applicability_binding",
    )
    validation_failed = False
    try:
        reconstructed = EvidenceScopeBinding(
            campaign,
            query,
            observation,
            intended,
            measurement,
        )
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failed = True
        reconstructed = None
    if validation_failed or reconstructed is None:
        raise _invalid(path)
    return reconstructed


def _reconstruct_nested_record(value: object, expected: type[T], path: str) -> T:
    checked = _exact(value, expected, path)
    validation_failure: tuple[str, str] | None = None
    try:
        reconstructed = replace(checked)
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
        reconstructed = None
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
        reconstructed = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstructed is None:
        raise _invalid(path)
    return reconstructed


def _reconstruct_any_top_ref(value: object, path: str) -> object:
    if not is_top_level_ref(value):
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    validation_failure: tuple[str, str] | None = None
    try:
        reconstructed = reconstruct_top_level_ref(value)
    except AuthoringError as error:
        nested_path = error.path if error.path.startswith("/") else ""
        validation_failure = (
            GeneratorInputCode.INVALID_VALUE.value,
            f"{path}{nested_path}",
        )
        reconstructed = None
    except (AttributeError, TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
        reconstructed = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstructed is None:
        raise _invalid(path)
    return reconstructed


def _reconstruct_top_ref(
    value: object,
    expected: type[T],
    path: str,
    *,
    challenge_key: ChallengeKey,
) -> T:
    _exact(value, expected, path)
    reconstructed = _reconstruct_any_top_ref(value, path)
    if type(reconstructed) is not expected:
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    if reconstructed.challenge_key != challenge_key:
        raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
    return reconstructed


def _top(value: object, expected: type[T], path: str, challenge: ChallengeKey) -> T:
    return _reconstruct_top_ref(
        value,
        expected,
        path,
        challenge_key=challenge,
    )


def _generator_domain_ref(
    value: object,
    expected: type[T],
    path: str,
    challenge: ChallengeKey,
) -> T:
    if expected is GeneratorReplayCommitmentRef:
        result = _exact(
            _reconstruct_replay_ref(value, challenge_key=challenge),
            expected,
            path,
        )
    else:
        result = _exact(reconstruct_generator_ref(value), expected, path)
    if result.challenge_key != challenge:
        raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
    return result


def _copy_role_key(value: object, path: str = "/role_key") -> RoleKey:
    if type(value) is not RoleKey:
        raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
    try:
        return RoleKey(value.value)
    except (TypeError, ValueError):
        pass
    raise _invalid(path)


class GeneratorEnvironmentClass(str, Enum):
    FIXTURE_ONLY = "FIXTURE_ONLY"


class SourceMaterializationState(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PAYLOAD_AVAILABLE = "PAYLOAD_AVAILABLE"
    NO_PAYLOAD = "NO_PAYLOAD"


MaterializationState = SourceMaterializationState


class GeneratorOutcomeKind(str, Enum):
    VALID_GENERATED = "VALID_GENERATED"
    REGISTERED_EXCLUSION = "REGISTERED_EXCLUSION"
    GENERATOR_NONCONFORMANCE = "GENERATOR_NONCONFORMANCE"
    INVALID_CONSTRUCTION = "INVALID_CONSTRUCTION"
    CENSORED_CASE = "CENSORED_CASE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class GeneratorTerminalStage(str, Enum):
    CONSTRUCTION_COMPATIBILITY = "CONSTRUCTION_COMPATIBILITY"
    CONTEXT_ACQUISITION = "CONTEXT_ACQUISITION"
    DERIVATION = "DERIVATION"
    MATERIALIZATION = "MATERIALIZATION"
    SUPPORT_AUTHORITY = "SUPPORT_AUTHORITY"
    CASE_CONSTRUCTION = "CASE_CONSTRUCTION"
    GRAPH_VALIDATION = "GRAPH_VALIDATION"
    CENSORING_AUTHORITY = "CENSORING_AUTHORITY"
    CENSORING_COMPLETION = "CENSORING_COMPLETION"
    ATTEMPT_ACCOUNTING_AUTHORITY = "ATTEMPT_ACCOUNTING_AUTHORITY"


class FailureOccurrenceEvidenceCategory(str, Enum):
    AUDIT_EVIDENCE = "AUDIT_EVIDENCE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class RecordRefBindingTag(str, Enum):
    BOUND = "BOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GeneratorInvocationOutputKind(str, Enum):
    FINAL = "FINAL"
    PENDING_SUCCESSOR = "PENDING_SUCCESSOR"


class ApplicabilityReasonKind(str, Enum):
    OUTCOME_REPLACEMENT_INAPPLICABLE = "OUTCOME_REPLACEMENT_INAPPLICABLE"
    REPLACEMENT_TRIGGER_INAPPLICABLE = "REPLACEMENT_TRIGGER_INAPPLICABLE"
    REPLACEMENT_LINEAGE_NOT_EXECUTED = "REPLACEMENT_LINEAGE_NOT_EXECUTED"
    SUCCESSOR_AUTHORIZATION_INAPPLICABLE = "SUCCESSOR_AUTHORIZATION_INAPPLICABLE"
    SUCCESSOR_EXECUTION_INAPPLICABLE = "SUCCESSOR_EXECUTION_INAPPLICABLE"
    DENOMINATOR_EFFECT_INAPPLICABLE = "DENOMINATOR_EFFECT_INAPPLICABLE"
    PENDING_ATTEMPT_INAPPLICABLE = "PENDING_ATTEMPT_INAPPLICABLE"
    RESULT_CASE_INAPPLICABLE = "RESULT_CASE_INAPPLICABLE"
    CONSTRUCTED_CASE_INAPPLICABLE = "CONSTRUCTED_CASE_INAPPLICABLE"
    SUPPORT_DECISION_INAPPLICABLE = "SUPPORT_DECISION_INAPPLICABLE"
    CENSORING_VERDICT_INAPPLICABLE = "CENSORING_VERDICT_INAPPLICABLE"
    CENSORING_DECISION_INAPPLICABLE = "CENSORING_DECISION_INAPPLICABLE"
    DISPOSITION_INAPPLICABLE = "DISPOSITION_INAPPLICABLE"
    TERMINAL_REASON_INAPPLICABLE = "TERMINAL_REASON_INAPPLICABLE"
    FAILURE_BINDING_INAPPLICABLE = "FAILURE_BINDING_INAPPLICABLE"


@dataclass(frozen=True, slots=True, repr=False)
class RecordRefPair:
    record: object
    ref: object

    def __post_init__(self) -> None:
        if type(self) is not RecordRefPair:
            raise _invalid("/pair", GeneratorInputCode.WRONG_TYPE)
        if self.record is None or self.ref is None:
            raise _invalid("/pair", GeneratorInputCode.INCOMPLETE_BINDING)
        validation_failure: tuple[str, str] | None = None
        try:
            if is_generator_ref(self.ref):
                from .canonical import verify_canonical_ref

                verify_canonical_ref(self.record, self.ref)
            else:
                to_ref = getattr(self.record, "to_ref", None)
                if not callable(to_ref) or to_ref() != self.ref:
                    raise _invalid("/pair", GeneratorInputCode.STALE_BINDING)
        except GeneratorValidationError as error:
            validation_failure = (error.code, error.path)
        except (AuthoringError, TypeError, ValueError):
            validation_failure = (GeneratorInputCode.STALE_BINDING.value, "/pair")
        if validation_failure is not None:
            raise GeneratorValidationError(
                validation_failure[0],
                path=validation_failure[1],
            )

    def __repr__(self) -> str:
        return "RecordRefPair(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected record-ref pairs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected record-ref pairs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class RecordRefBinding:
    tag: RecordRefBindingTag
    pair: RecordRefPair | None
    reason_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not RecordRefBinding:
            raise _invalid("/binding", GeneratorInputCode.WRONG_TYPE)
        _exact_enum(self.tag, RecordRefBindingTag, "/tag")
        if self.tag is RecordRefBindingTag.BOUND:
            _exact(self.pair, RecordRefPair, "/pair")
            if self.reason_ref is not None:
                raise _invalid("/reason_ref")
        else:
            if self.pair is not None:
                raise _invalid("/pair")
            object.__setattr__(
                self,
                "reason_ref",
                _owner(self.reason_ref, "applicability_reason", "/reason_ref"),
            )

    @classmethod
    def bound(cls, record: object, ref: object) -> RecordRefBinding:
        return cls(RecordRefBindingTag.BOUND, RecordRefPair(record, ref), None)

    @classmethod
    def not_applicable(cls, reason_ref: object) -> RecordRefBinding:
        return cls(RecordRefBindingTag.NOT_APPLICABLE, None, reason_ref)

    @property
    def is_bound(self) -> bool:
        return self.tag is RecordRefBindingTag.BOUND

    def __repr__(self) -> str:
        return "RecordRefBinding(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected record-ref bindings cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected record-ref bindings cannot be pickled")


@dataclass(frozen=True, slots=True)
class GeneratorImplementationManifest:
    implementation_id: str
    implementation_version: str
    package: str
    runtime_contract_version: str
    canonical_profile: str
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    latent_codec_id: str

    def __post_init__(self) -> None:
        if type(self) is not GeneratorImplementationManifest:
            raise _invalid("/implementation_manifest", GeneratorInputCode.WRONG_TYPE)
        if self.implementation_id != "carbon_generators_burgers_fixture":
            raise _invalid("/implementation_id")
        if self.implementation_version != "1.0":
            raise _invalid("/implementation_version")
        if self.package != "carbon.generators.burgers":
            raise _invalid("/package")
        if self.runtime_contract_version != "0.1":
            raise _invalid("/runtime_contract_version")
        if self.canonical_profile != "carbon_generator_runtime_canonical_v1":
            raise _invalid("/canonical_profile")
        _exact(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            "/fixture_configuration_ref",
        )
        if self.latent_codec_id != "carbon.b03.burgers.fixture-latent.v1":
            raise _invalid("/latent_codec_id")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    @property
    def implementation_digest(self) -> str:
        from .canonical import canonical_content_digest

        return canonical_content_digest(self)


@dataclass(frozen=True, slots=True)
class GeneratorEnvironmentDescriptor:
    challenge_key: ChallengeKey
    environment_id: str
    environment_version: str
    python_implementation: str
    python_version: str
    platform_tag: str
    dependency_lock_digest: str
    environment_class: GeneratorEnvironmentClass

    def __post_init__(self) -> None:
        if type(self) is not GeneratorEnvironmentDescriptor:
            raise _invalid("/environment", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "environment_id", _identifier(self.environment_id, "/environment_id")
        )
        object.__setattr__(
            self,
            "environment_version",
            _version(self.environment_version, "/environment_version"),
        )
        if (
            type(self.python_implementation) is not str
            or not self.python_implementation
        ):
            raise _invalid("/python_implementation")
        object.__setattr__(
            self, "python_version", _version(self.python_version, "/python_version")
        )
        if type(self.platform_tag) is not str or not self.platform_tag:
            raise _invalid("/platform_tag")
        object.__setattr__(
            self,
            "dependency_lock_digest",
            _digest(self.dependency_lock_digest, "/dependency_lock_digest"),
        )
        _exact_enum(
            self.environment_class, GeneratorEnvironmentClass, "/environment_class"
        )
        if self.environment_class is not GeneratorEnvironmentClass.FIXTURE_ONLY:
            raise _invalid("/environment_class")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GeneratorEnvironmentRef:
        from .canonical import _record_ref

        return _record_ref(self, GeneratorEnvironmentRef)


@dataclass(frozen=True, slots=True)
class GeneratorDescriptor:
    challenge_key: ChallengeKey
    generator_id: str
    generator_version: str
    implementation_digest: str
    environment_ref: GeneratorEnvironmentRef
    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    supported_physical_system_ref: PhysicalSystemSpecRef
    supported_candidate_output_ref: CandidateOutputContractRef
    supported_primary_population_ref: InstanceDistributionContractRef
    supported_selection_population_ref: InstanceDistributionContractRef

    def __post_init__(self) -> None:
        if type(self) is not GeneratorDescriptor:
            raise _invalid("/generator", GeneratorInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self, "generator_id", _identifier(self.generator_id, "/generator_id")
        )
        object.__setattr__(
            self,
            "generator_version",
            _version(self.generator_version, "/generator_version"),
        )
        object.__setattr__(
            self,
            "implementation_digest",
            _digest(self.implementation_digest, "/implementation_digest"),
        )
        _generator_domain_ref(
            self.environment_ref, GeneratorEnvironmentRef, "/environment_ref", challenge
        )
        object.__setattr__(
            self,
            "fixture_registration_ref",
            _owner(
                self.fixture_registration_ref,
                "fixture_registration",
                "/fixture_registration_ref",
                challenge_key=challenge,
            ),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_tuple(
                self.source_provenance_refs,
                "provenance",
                "/source_provenance_refs",
                challenge_key=challenge,
                nonempty=True,
            ),
        )
        _generator_domain_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            "/fixture_configuration_ref",
            challenge,
        )
        for name, expected in (
            ("supported_physical_system_ref", PhysicalSystemSpecRef),
            ("supported_candidate_output_ref", CandidateOutputContractRef),
            ("supported_primary_population_ref", InstanceDistributionContractRef),
            ("supported_selection_population_ref", InstanceDistributionContractRef),
        ):
            _top(getattr(self, name), expected, f"/{name}", challenge)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> object:
        from .refs import generator_ref

        return generator_ref(self)


@dataclass(frozen=True, slots=True)
class GenerationRoleBinding:
    sampling_role: SamplingRole
    seed_domain: SeedDomain
    role_key: RoleKey
    sampling_plan_ref: SamplingPlanRef

    def __post_init__(self) -> None:
        if type(self) is not GenerationRoleBinding:
            raise _invalid("/role_binding", GeneratorInputCode.WRONG_TYPE)
        _exact_enum(self.sampling_role, SamplingRole, "/sampling_role")
        _exact_enum(self.seed_domain, SeedDomain, "/seed_domain")
        object.__setattr__(self, "role_key", _copy_role_key(self.role_key))
        object.__setattr__(
            self,
            "sampling_plan_ref",
            _exact(
                _reconstruct_any_top_ref(
                    self.sampling_plan_ref,
                    "/sampling_plan_ref",
                ),
                SamplingPlanRef,
                "/sampling_plan_ref",
            ),
        )
        expected = {
            SamplingRole.OFFICIAL_EVALUATION: SeedDomain.OFFICIAL_EVAL,
            SamplingRole.STRESS: SeedDomain.OFFICIAL_STRESS,
            SamplingRole.PRACTICE: SeedDomain.OFFICIAL_TRAIN,
        }.get(self.sampling_role)
        if expected is None or self.seed_domain is not expected:
            raise _invalid("/seed_domain")
        if self.role_key.value != "generator_sampling":
            raise _invalid("/role_key")


@dataclass(frozen=True, slots=True, repr=False)
class CaseConstructionBinding:
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[CanonicalChallengeCaseRef]
    related_population_bindings: tuple[RelatedPopulationBinding, ...]
    case_representation_ref: object
    query_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    observation_population_binding: ApplicabilityBinding[
        InstanceDistributionContractRef
    ]
    evidence_campaign_binding: ApplicabilityBinding[object]
    intended_slot_binding: ApplicabilityBinding[object]
    prospective_censoring_policy_binding: ApplicabilityBinding[object]
    applicability_bindings: tuple[object, ...]
    disclosure_class: DisclosureClass
    disclosure_contract: DisclosureContract
    case_provenance_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not CaseConstructionBinding:
            raise _invalid("/case_construction", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self, "object_version", _version(self.object_version, "/object_version")
        )
        object.__setattr__(
            self,
            "supersedes",
            _reconstruct_applicability_top(
                self.supersedes,
                CanonicalChallengeCaseRef,
                "/supersedes",
            ),
        )
        related_values = _exact_tuple(
            self.related_population_bindings,
            RelatedPopulationBinding,
            "/related_population_bindings",
        )
        reconstructed_related = tuple(
            RelatedPopulationBinding(
                _exact(
                    _reconstruct_any_top_ref(
                        item.population_ref,
                        f"/related_population_bindings/{index}/population_ref",
                    ),
                    InstanceDistributionContractRef,
                    f"/related_population_bindings/{index}/population_ref",
                ),
                _owner(
                    item.relationship_ref,
                    "population_relationship",
                    f"/related_population_bindings/{index}/relationship_ref",
                ),
            )
            for index, item in enumerate(related_values)
        )
        if len(set(reconstructed_related)) != len(reconstructed_related):
            raise _invalid("/related_population_bindings")
        object.__setattr__(
            self,
            "related_population_bindings",
            reconstructed_related,
        )
        object.__setattr__(
            self,
            "case_representation_ref",
            _owner(
                self.case_representation_ref,
                "representation",
                "/case_representation_ref",
            ),
        )
        for name in ("query_population_binding", "observation_population_binding"):
            object.__setattr__(
                self,
                name,
                _reconstruct_applicability_top(
                    getattr(self, name),
                    InstanceDistributionContractRef,
                    f"/{name}",
                ),
            )
        for name, kind in (
            ("evidence_campaign_binding", "evidence_campaign"),
            ("intended_slot_binding", "protected_intended_slot"),
            ("prospective_censoring_policy_binding", "censoring_policy"),
        ):
            object.__setattr__(
                self,
                name,
                _reconstruct_applicability_owner(
                    getattr(self, name),
                    kind,
                    f"/{name}",
                ),
            )
        object.__setattr__(
            self,
            "applicability_bindings",
            _owner_tuple(
                self.applicability_bindings,
                "applicability",
                "/applicability_bindings",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_class",
            _exact_enum(self.disclosure_class, DisclosureClass, "/disclosure_class"),
        )
        object.__setattr__(
            self,
            "disclosure_contract",
            _reconstruct_disclosure_contract(
                self.disclosure_contract,
                "/disclosure_contract",
            ),
        )
        object.__setattr__(
            self,
            "case_provenance_refs",
            _owner_tuple(
                self.case_provenance_refs,
                "provenance",
                "/case_provenance_refs",
                nonempty=True,
            ),
        )

    def __repr__(self) -> str:
        return "CaseConstructionBinding(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected case-construction bindings cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected case-construction bindings cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class FixtureLoadingBinding:
    origin_evidence_ref: object
    audit_evidence_refs: tuple[object, ...]
    composition_audit_ref: object
    fixture_unqualified_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not FixtureLoadingBinding:
            raise _invalid("/fixture_loading", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(
            self,
            "origin_evidence_ref",
            _owner(
                self.origin_evidence_ref,
                "authoring_origin_evidence",
                "/origin_evidence_ref",
            ),
        )
        object.__setattr__(
            self,
            "audit_evidence_refs",
            _owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "/audit_evidence_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "composition_audit_ref",
            _owner(
                self.composition_audit_ref,
                "origin_composition_audit",
                "/composition_audit_ref",
            ),
        )
        object.__setattr__(
            self,
            "fixture_unqualified_reason_ref",
            _owner(
                self.fixture_unqualified_reason_ref,
                "applicability_reason",
                "/fixture_unqualified_reason_ref",
            ),
        )

    @property
    def qualification_evidence(self) -> ApplicabilityBinding[object]:
        return ApplicabilityBinding.not_applicable(self.fixture_unqualified_reason_ref)

    def __repr__(self) -> str:
        return "FixtureLoadingBinding(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected fixture-loading bindings cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected fixture-loading bindings cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class DispositionConstructionBinding:
    evidence_scope: EvidenceScopeBinding
    policy_authority_ref: object
    audit_evidence_refs: tuple[object, ...]
    downstream_use_restrictions: tuple[object, ...]
    disclosure_contract: DisclosureContract
    case_inapplicable_reason_ref: object
    attempt_inapplicable_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not DispositionConstructionBinding:
            raise _invalid("/disposition_construction", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(
            self,
            "evidence_scope",
            _reconstruct_evidence_scope(self.evidence_scope, "/evidence_scope"),
        )
        object.__setattr__(
            self,
            "policy_authority_ref",
            _owner(
                self.policy_authority_ref, "policy_authority", "/policy_authority_ref"
            ),
        )
        object.__setattr__(
            self,
            "audit_evidence_refs",
            _owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "/audit_evidence_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "downstream_use_restrictions",
            _owner_tuple(
                self.downstream_use_restrictions,
                "restriction",
                "/downstream_use_restrictions",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_contract",
            _reconstruct_disclosure_contract(
                self.disclosure_contract,
                "/disclosure_contract",
            ),
        )
        for name in ("case_inapplicable_reason_ref", "attempt_inapplicable_reason_ref"):
            object.__setattr__(
                self,
                name,
                _owner(getattr(self, name), "applicability_reason", f"/{name}"),
            )

    def __repr__(self) -> str:
        return "DispositionConstructionBinding(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected disposition-construction bindings cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected disposition-construction bindings cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedGeneratorAuthoringBundle:
    physical_system: object
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output: object
    candidate_output_ref: CandidateOutputContractRef
    primary_population: object
    primary_population_ref: InstanceDistributionContractRef
    selection_population: object
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan: object
    sampling_plan_ref: SamplingPlanRef
    resolved_dependencies: tuple[tuple[object, object], ...]
    loaded_dependencies: tuple[LoadedAuthoringArtifact, ...]

    def __post_init__(self) -> None:
        if type(self) is not ResolvedGeneratorAuthoringBundle:
            raise _invalid("/authoring_bundle", GeneratorInputCode.WRONG_TYPE)
        pairs = (
            (self.physical_system, self.physical_system_ref),
            (self.candidate_output, self.candidate_output_ref),
            (self.primary_population, self.primary_population_ref),
            (self.selection_population, self.selection_population_ref),
            (self.sampling_plan, self.sampling_plan_ref),
        )
        challenge: ChallengeKey | None = None
        for obj, ref in pairs:
            if not is_top_level_ref(ref):
                raise _invalid("/authoring_bundle", GeneratorInputCode.WRONG_TYPE)
            try:
                observed_ref = obj.to_ref()
            except Exception:  # noqa: BLE001 - protected hostile object boundary.
                observed_ref = None
            if observed_ref != ref:
                raise _invalid("/authoring_bundle", GeneratorInputCode.STALE_BINDING)
            challenge = ref.challenge_key if challenge is None else challenge
            if ref.challenge_key != challenge:
                raise _invalid("/authoring_bundle", GeneratorInputCode.CROSS_CHALLENGE)
        resolved = _exact_tuple(
            self.resolved_dependencies, tuple, "/resolved_dependencies", unique=True
        )
        for pair in resolved:
            if len(pair) != 2 or not is_top_level_ref(pair[0]):
                raise _invalid(
                    "/resolved_dependencies", GeneratorInputCode.STALE_BINDING
                )
            try:
                observed_ref = pair[1].to_ref()
            except Exception:  # noqa: BLE001 - protected hostile object boundary.
                observed_ref = None
            if observed_ref != pair[0]:
                raise _invalid(
                    "/resolved_dependencies", GeneratorInputCode.STALE_BINDING
                )
        loaded = _exact_tuple(
            self.loaded_dependencies,
            LoadedAuthoringArtifact,
            "/loaded_dependencies",
            unique=True,
        )
        object.__setattr__(self, "resolved_dependencies", resolved)
        object.__setattr__(self, "loaded_dependencies", loaded)

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.physical_system_ref.challenge_key

    def objects_by_ref(self) -> dict[object, object]:
        result = {ref: obj for ref, obj in self.resolved_dependencies}
        for obj, ref in (
            (self.physical_system, self.physical_system_ref),
            (self.candidate_output, self.candidate_output_ref),
            (self.primary_population, self.primary_population_ref),
            (self.selection_population, self.selection_population_ref),
            (self.sampling_plan, self.sampling_plan_ref),
        ):
            result[ref] = obj
        return result

    def __repr__(self) -> str:
        return "ResolvedGeneratorAuthoringBundle(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected authoring bundles cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected authoring bundles cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class LoadedDependencyIdentity:
    expected_ref: object
    recomputed_ref: object
    origin_tag: OriginTag
    origin_evidence_ref: object
    source_provenance_refs: tuple[object, ...]
    audit_evidence_refs: tuple[object, ...]
    qualification_evidence: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        if type(self) is not LoadedDependencyIdentity:
            raise _invalid("/loaded_dependency", GeneratorInputCode.WRONG_TYPE)
        expected_ref = _reconstruct_any_top_ref(
            self.expected_ref,
            "/expected_ref",
        )
        recomputed_ref = _reconstruct_any_top_ref(
            self.recomputed_ref,
            "/recomputed_ref",
        )
        if type(recomputed_ref) is not type(expected_ref):
            raise _invalid("/recomputed_ref", GeneratorInputCode.WRONG_TYPE)
        if expected_ref != recomputed_ref:
            raise _invalid("/recomputed_ref", GeneratorInputCode.STALE_BINDING)
        origin_tag = _exact_enum(self.origin_tag, OriginTag, "/origin_tag")
        object.__setattr__(
            self,
            "origin_evidence_ref",
            _owner(
                self.origin_evidence_ref,
                "authoring_origin_evidence",
                "/origin_evidence_ref",
            ),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_tuple(
                self.source_provenance_refs,
                "provenance",
                "/source_provenance_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "audit_evidence_refs",
            _owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "/audit_evidence_refs",
                nonempty=True,
            ),
        )
        qualification = _exact(
            self.qualification_evidence,
            ApplicabilityBinding,
            "/qualification_evidence",
        )
        qualification_tag = _exact_enum(
            qualification.tag,
            ApplicabilityTag,
            "/qualification_evidence/tag",
        )
        qualification_ref = _owner(
            qualification.value,
            (
                "qualification_evidence_bundle"
                if qualification_tag is ApplicabilityTag.BOUND
                else "applicability_reason"
            ),
            "/qualification_evidence/value",
        )
        object.__setattr__(self, "expected_ref", expected_ref)
        object.__setattr__(self, "recomputed_ref", recomputed_ref)
        object.__setattr__(self, "origin_tag", origin_tag)
        object.__setattr__(
            self,
            "qualification_evidence",
            ApplicabilityBinding(qualification_tag, qualification_ref),
        )

    @classmethod
    def from_loaded(cls, value: LoadedAuthoringArtifact) -> LoadedDependencyIdentity:
        _exact(value, LoadedAuthoringArtifact, "/loaded_dependency")
        return cls(
            value.expected_ref,
            value.recomputed_ref,
            value.origin.tag,
            value.origin_evidence_ref,
            value.source_provenance_refs,
            value.audit_evidence_refs,
            value.qualification_evidence,
        )

    def __repr__(self) -> str:
        return "LoadedDependencyIdentity(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected loaded-dependency identities cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected loaded-dependency identities cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingFallback:
    authority_failure_ref: object
    denominator_unavailable_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not AttemptAccountingFallback:
            raise _invalid(
                "/attempt_accounting_fallback", GeneratorInputCode.WRONG_TYPE
            )
        object.__setattr__(
            self,
            "authority_failure_ref",
            _owner(
                self.authority_failure_ref,
                "infrastructure_failure",
                "/authority_failure_ref",
            ),
        )
        object.__setattr__(
            self,
            "denominator_unavailable_reason_ref",
            _owner(
                self.denominator_unavailable_reason_ref,
                "applicability_reason",
                "/denominator_unavailable_reason_ref",
            ),
        )

    def __repr__(self) -> str:
        return "AttemptAccountingFallback(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected attempt-accounting fallbacks cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected attempt-accounting fallbacks cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class NamedApplicabilityReason:
    kind: ApplicabilityReasonKind
    reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not NamedApplicabilityReason:
            raise _invalid("/applicability_reason", GeneratorInputCode.WRONG_TYPE)
        _exact_enum(self.kind, ApplicabilityReasonKind, "/kind")
        object.__setattr__(
            self,
            "reason_ref",
            _owner(self.reason_ref, "applicability_reason", "/reason_ref"),
        )

    def __repr__(self) -> str:
        return "NamedApplicabilityReason(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected named applicability reasons cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected named applicability reasons cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class NamedConformanceFallback:
    fallback_id: str
    fallback_ref: object

    def __post_init__(self) -> None:
        if type(self) is not NamedConformanceFallback:
            raise _invalid("/conformance_fallback", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(
            self, "fallback_id", _identifier(self.fallback_id, "/fallback_id")
        )
        if not is_owner_ref(self.fallback_ref):
            raise _invalid("/fallback_ref", GeneratorInputCode.WRONG_TYPE)

    def __repr__(self) -> str:
        return "NamedConformanceFallback(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected named conformance fallbacks cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected named conformance fallbacks cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorFailureReason:
    challenge_key: ChallengeKey
    reason_id: str
    reason_version: str
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    reason_code: str
    occurrence_evidence_category: FailureOccurrenceEvidenceCategory

    def __post_init__(self) -> None:
        if type(self) is not GeneratorFailureReason:
            raise _invalid("/failure_reason", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "reason_id", _identifier(self.reason_id, "/reason_id"))
        if self.reason_version != "1.0":
            raise _invalid("/reason_version")
        _exact_enum(self.outcome_kind, GeneratorOutcomeKind, "/outcome_kind")
        if self.outcome_kind not in {
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        }:
            raise _invalid("/outcome_kind")
        _exact_enum(self.terminal_stage, GeneratorTerminalStage, "/terminal_stage")
        object.__setattr__(
            self, "reason_code", _identifier(self.reason_code, "/reason_code")
        )
        _exact_enum(
            self.occurrence_evidence_category,
            FailureOccurrenceEvidenceCategory,
            "/occurrence_evidence_category",
        )
        observed = (
            self.outcome_kind,
            self.terminal_stage,
            self.reason_id,
            self.reason_code,
            self.occurrence_evidence_category,
        )
        if observed not in _FAILURE_CATALOG_SCHEMA:
            raise _invalid("/failure_reason")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(replace(self))

    def to_ref(self) -> GeneratorFailureReasonRef:
        from .canonical import _record_ref

        return _record_ref(replace(self), GeneratorFailureReasonRef)

    def __repr__(self) -> str:
        return "GeneratorFailureReason(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator failure reasons cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorFailureCatalogEntry:
    reason: GeneratorFailureReason
    reason_ref: GeneratorFailureReasonRef
    generation_failure_alias_binding: ApplicabilityBinding[object]
    replacement_eligible_generation_failure_alias_binding: ApplicabilityBinding[object]
    occurrence_evidence_fallback: object

    def __post_init__(self) -> None:
        if type(self) is not GeneratorFailureCatalogEntry:
            raise _invalid("/failure_catalog_entry", GeneratorInputCode.WRONG_TYPE)
        reason = replace(_exact(self.reason, GeneratorFailureReason, "/reason"))
        reason_ref = _generator_domain_ref(
            self.reason_ref,
            GeneratorFailureReasonRef,
            "/reason_ref",
            reason.challenge_key,
        )
        if reason.to_ref() != reason_ref:
            raise _invalid("/reason_ref", GeneratorInputCode.STALE_BINDING)
        generation_alias, replacement_alias = _reconstruct_failure_aliases(
            reason,
            self.generation_failure_alias_binding,
            self.replacement_eligible_generation_failure_alias_binding,
            challenge_key=reason.challenge_key,
            path="/failure_catalog_entry",
        )
        expected_kind = (
            "infrastructure_failure"
            if reason.occurrence_evidence_category
            is FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE
            else "audit_evidence"
        )
        fallback = _owner(
            self.occurrence_evidence_fallback,
            expected_kind,
            "/occurrence_evidence_fallback",
            challenge_key=reason.challenge_key,
        )
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "reason_ref", reason_ref)
        object.__setattr__(
            self,
            "generation_failure_alias_binding",
            generation_alias,
        )
        object.__setattr__(
            self,
            "replacement_eligible_generation_failure_alias_binding",
            replacement_alias,
        )
        object.__setattr__(self, "occurrence_evidence_fallback", fallback)

    def __repr__(self) -> str:
        return "GeneratorFailureCatalogEntry(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator failure catalog entries cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorFailureOccurrence:
    challenge_key: ChallengeKey
    request_ref: GeneratorRequestRef
    source_event_ref: object
    reason: GeneratorFailureReason
    reason_ref: GeneratorFailureReasonRef
    generation_failure_alias_binding: ApplicabilityBinding[object]
    replacement_eligible_generation_failure_alias_binding: ApplicabilityBinding[object]
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    occurrence_evidence_binding: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        if type(self) is not GeneratorFailureOccurrence:
            raise _invalid("/failure_occurrence", GeneratorInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        request_ref = _generator_domain_ref(
            self.request_ref,
            GeneratorRequestRef,
            "/request_ref",
            challenge,
        )
        object.__setattr__(
            self,
            "source_event_ref",
            _owner(
                self.source_event_ref,
                "generation_event",
                "/source_event_ref",
                challenge_key=challenge,
            ),
        )
        reason = replace(_exact(self.reason, GeneratorFailureReason, "/reason"))
        reason_ref = _generator_domain_ref(
            self.reason_ref,
            GeneratorFailureReasonRef,
            "/reason_ref",
            challenge,
        )
        if reason.challenge_key != challenge or reason.to_ref() != reason_ref:
            raise _invalid("/reason_ref", GeneratorInputCode.STALE_BINDING)
        generation_alias, replacement_alias = _reconstruct_failure_aliases(
            reason,
            self.generation_failure_alias_binding,
            self.replacement_eligible_generation_failure_alias_binding,
            challenge_key=challenge,
            path="/failure_occurrence",
        )
        outcome = _exact_enum(
            self.outcome_kind,
            GeneratorOutcomeKind,
            "/outcome_kind",
        )
        stage = _exact_enum(
            self.terminal_stage,
            GeneratorTerminalStage,
            "/terminal_stage",
        )
        if outcome is not reason.outcome_kind or stage is not reason.terminal_stage:
            raise _invalid("/terminal_stage")
        evidence_binding = _exact(
            self.occurrence_evidence_binding,
            ApplicabilityBinding,
            "/occurrence_evidence_binding",
        )
        if evidence_binding.tag is not ApplicabilityTag.BOUND:
            raise _invalid("/occurrence_evidence_binding")
        evidence_kind = (
            "infrastructure_failure"
            if reason.occurrence_evidence_category
            is FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE
            else "audit_evidence"
        )
        evidence = _owner(
            evidence_binding.value,
            evidence_kind,
            "/occurrence_evidence_binding/value",
            challenge_key=challenge,
        )
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "reason_ref", reason_ref)
        object.__setattr__(
            self,
            "generation_failure_alias_binding",
            generation_alias,
        )
        object.__setattr__(
            self,
            "replacement_eligible_generation_failure_alias_binding",
            replacement_alias,
        )
        object.__setattr__(self, "outcome_kind", outcome)
        object.__setattr__(self, "terminal_stage", stage)
        object.__setattr__(
            self,
            "occurrence_evidence_binding",
            ApplicabilityBinding.bound(evidence),
        )

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(replace(self))

    def to_ref(self) -> GeneratorFailureOccurrenceRef:
        from .canonical import _record_ref

        return _record_ref(replace(self), GeneratorFailureOccurrenceRef)

    def __repr__(self) -> str:
        return "GeneratorFailureOccurrence(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator failure occurrences cannot be pickled")


_ATTEMPT_ACCOUNTING_REASON_SCHEMA = (
    ApplicabilityReasonKind.OUTCOME_REPLACEMENT_INAPPLICABLE,
    ApplicabilityReasonKind.REPLACEMENT_TRIGGER_INAPPLICABLE,
    ApplicabilityReasonKind.REPLACEMENT_LINEAGE_NOT_EXECUTED,
    ApplicabilityReasonKind.SUCCESSOR_AUTHORIZATION_INAPPLICABLE,
    ApplicabilityReasonKind.SUCCESSOR_EXECUTION_INAPPLICABLE,
    ApplicabilityReasonKind.DENOMINATOR_EFFECT_INAPPLICABLE,
    ApplicabilityReasonKind.PENDING_ATTEMPT_INAPPLICABLE,
)
_RESULT_REASON_SCHEMA = (
    ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
    ApplicabilityReasonKind.CONSTRUCTED_CASE_INAPPLICABLE,
    ApplicabilityReasonKind.SUPPORT_DECISION_INAPPLICABLE,
    ApplicabilityReasonKind.CENSORING_VERDICT_INAPPLICABLE,
    ApplicabilityReasonKind.CENSORING_DECISION_INAPPLICABLE,
    ApplicabilityReasonKind.DISPOSITION_INAPPLICABLE,
    ApplicabilityReasonKind.TERMINAL_REASON_INAPPLICABLE,
    ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
)
_CONFORMANCE_FALLBACK_SCHEMA = (
    "payload_facts_construction_compatibility",
    "payload_facts_context_acquisition",
    "payload_facts_derivation",
    "payload_facts_materialization",
    "support_decision_construction_compatibility",
    "support_decision_context_acquisition",
    "support_decision_derivation",
    "support_decision_materialization",
    "validated_case_facts_construction_compatibility",
    "validated_case_facts_context_acquisition",
    "validated_case_facts_derivation",
    "validated_case_facts_materialization",
    "validated_case_facts_support_authority",
    "validated_case_facts_case_construction",
    "validated_case_facts_graph_validation",
    "support_decision_owner_unavailable",
)
_FAILURE_CATALOG_SCHEMA = (
    (
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_sampler_contract_violation",
        "sampler_contract_violation",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_outside_registered_support",
        "outside_registered_support",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY,
        "b03_construction_compatibility_failed",
        "construction_compatibility_failed",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_failed",
        "case_construction_failed",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_authoring_graph_invalid",
        "authoring_graph_invalid",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CONTEXT_ACQUISITION,
        "b03_context_acquisition_unavailable",
        "context_acquisition_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.DERIVATION,
        "b03_seed_derivation_unavailable",
        "seed_derivation_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_materialization_infrastructure_failure",
        "materialization_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_support_authority_unavailable",
        "support_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_infrastructure_failure",
        "case_construction_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CENSORING_AUTHORITY,
        "b03_censoring_authority_unavailable",
        "censoring_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
        "b03_attempt_accounting_authority_unavailable",
        "attempt_accounting_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_graph_validation_infrastructure_failure",
        "graph_validation_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
)


def _reconstruct_named_reasons(
    value: object,
    expected: tuple[ApplicabilityReasonKind, ...],
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> tuple[NamedApplicabilityReason, ...]:
    values = _exact_tuple(
        value,
        NamedApplicabilityReason,
        path,
        nonempty=True,
    )
    if len(values) != len(expected) or tuple(item.kind for item in values) != expected:
        raise _invalid(path)
    reconstructed = tuple(
        NamedApplicabilityReason(
            _exact_enum(item.kind, ApplicabilityReasonKind, f"{path}/{index}/kind"),
            _owner(
                item.reason_ref,
                "applicability_reason",
                f"{path}/{index}/reason_ref",
                challenge_key=challenge_key,
            ),
        )
        for index, item in enumerate(values)
    )
    if len({item.reason_ref for item in reconstructed}) != len(reconstructed):
        raise _invalid(path)
    return reconstructed


def _reconstruct_runtime_ref(
    value: object,
    expected: type[T],
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> T:
    ref = _exact(value, expected, path)
    validation_failure: tuple[str, str] | None = None
    try:
        reconstructed = expected(
            ref.challenge_key,
            ref.content_digest,
            ref.schema_version,
            ref.canonicalization_profile,
        )
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
        reconstructed = None
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
        reconstructed = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstructed is None:
        raise _invalid(path)
    if reconstructed.challenge_key != challenge_key:
        raise _invalid(path, GeneratorInputCode.CROSS_CHALLENGE)
    return reconstructed


def _reconstruct_replay_ref(
    value: object,
    *,
    challenge_key: ChallengeKey,
) -> GeneratorReplayCommitmentRef:
    replay = _exact(value, GeneratorReplayCommitmentRef, "/replay_ref")
    validation_failure: tuple[str, str] | None = None
    try:
        reconstructed = GeneratorReplayCommitmentRef(
            replay.challenge_key,
            replay.replay_scheme_id,
            replay.replay_scheme_version,
            replay.reservation_issuer_ref,
            replay.commitment_digest,
        )
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
        reconstructed = None
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failure = (
            GeneratorInputCode.INVALID_VALUE.value,
            "/replay_ref",
        )
        reconstructed = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstructed is None:
        raise _invalid("/replay_ref")
    if reconstructed.challenge_key != challenge_key:
        raise _invalid("/replay_ref", GeneratorInputCode.CROSS_CHALLENGE)
    return reconstructed


def _reconstruct_conformance_fallbacks(
    value: object,
    *,
    challenge_key: ChallengeKey,
) -> tuple[NamedConformanceFallback, ...]:
    path = "/conformance_fallbacks"
    values = _exact_tuple(value, NamedConformanceFallback, path, nonempty=True)
    if (
        len(values) != len(_CONFORMANCE_FALLBACK_SCHEMA)
        or tuple(item.fallback_id for item in values) != _CONFORMANCE_FALLBACK_SCHEMA
    ):
        raise _invalid(path)
    reconstructed = tuple(
        NamedConformanceFallback(
            _identifier(item.fallback_id, f"{path}/{index}/fallback_id"),
            _owner(
                item.fallback_ref,
                (
                    "infrastructure_failure"
                    if item.fallback_id == "support_decision_owner_unavailable"
                    else "applicability_reason"
                ),
                f"{path}/{index}/fallback_ref",
                challenge_key=challenge_key,
            ),
        )
        for index, item in enumerate(values)
    )
    if len({item.fallback_ref for item in reconstructed}) != len(reconstructed):
        raise _invalid(path)
    return reconstructed


def _reconstruct_catalog_binding(
    value: object,
    *,
    bound_kind: str,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding[object]:
    binding = _exact(value, ApplicabilityBinding, path)
    tag = _exact_enum(binding.tag, ApplicabilityTag, f"{path}/tag")
    kind = bound_kind if tag is ApplicabilityTag.BOUND else "applicability_reason"
    checked = _owner(
        binding.value,
        kind,
        f"{path}/value",
        challenge_key=challenge_key,
    )
    return ApplicabilityBinding(tag, checked)


def _reconstruct_failure_aliases(
    reason: GeneratorFailureReason,
    generation_value: object,
    replacement_value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> tuple[ApplicabilityBinding[object], ApplicabilityBinding[object]]:
    generation = _reconstruct_catalog_binding(
        generation_value,
        bound_kind="generation_failure",
        challenge_key=challenge_key,
        path=f"{path}/generation_failure_alias_binding",
    )
    replacement = _reconstruct_catalog_binding(
        replacement_value,
        bound_kind="replacement_eligible_generation_failure_reason",
        challenge_key=challenge_key,
        path=(f"{path}/replacement_eligible_generation_failure_alias_binding"),
    )
    if reason.outcome_kind is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
        if not generation.is_bound or not replacement.is_bound:
            raise _invalid(path)
        pins = ("scope_binding", "object_id", "object_version", "content_digest")
        if (
            any(
                getattr(generation.value, name) != getattr(replacement.value, name)
                for name in pins
            )
            or generation.value.object_id != reason.reason_id
            or generation.value.object_version != reason.reason_version
            or generation.value.content_digest != reason.to_ref().content_digest
        ):
            raise _invalid(path, GeneratorInputCode.STALE_BINDING)
    elif (
        generation.is_bound
        or replacement.is_bound
        or generation.value != replacement.value
    ):
        raise _invalid(path)
    return generation, replacement


def _reconstruct_failure_catalog(
    value: object,
    *,
    challenge_key: ChallengeKey,
) -> tuple[GeneratorFailureCatalogEntry, ...]:
    path = "/failure_reason_catalog"
    values = _exact_tuple(value, GeneratorFailureCatalogEntry, path, nonempty=True)
    if len(values) != len(_FAILURE_CATALOG_SCHEMA):
        raise _invalid(path)
    reconstructed: list[GeneratorFailureCatalogEntry] = []
    for index, (item, expected) in enumerate(
        zip(values, _FAILURE_CATALOG_SCHEMA, strict=True)
    ):
        item_path = f"{path}/{index}"
        original_reason = _exact(
            item.reason,
            GeneratorFailureReason,
            f"{item_path}/reason",
        )
        reason = GeneratorFailureReason(
            original_reason.challenge_key,
            original_reason.reason_id,
            original_reason.reason_version,
            original_reason.outcome_kind,
            original_reason.terminal_stage,
            original_reason.reason_code,
            original_reason.occurrence_evidence_category,
        )
        if reason.challenge_key != challenge_key:
            raise _invalid(f"{item_path}/reason", GeneratorInputCode.CROSS_CHALLENGE)
        observed = (
            reason.outcome_kind,
            reason.terminal_stage,
            reason.reason_id,
            reason.reason_code,
            reason.occurrence_evidence_category,
        )
        if observed != expected or reason.reason_version != "1.0":
            raise _invalid(path)
        reason_ref = _generator_domain_ref(
            item.reason_ref,
            GeneratorFailureReasonRef,
            f"{item_path}/reason_ref",
            challenge_key,
        )
        if reason.to_ref() != reason_ref:
            raise _invalid(
                f"{item_path}/reason_ref",
                GeneratorInputCode.STALE_BINDING,
            )
        generation_alias = _reconstruct_catalog_binding(
            item.generation_failure_alias_binding,
            bound_kind="generation_failure",
            challenge_key=challenge_key,
            path=f"{item_path}/generation_failure_alias_binding",
        )
        replacement_alias = _reconstruct_catalog_binding(
            item.replacement_eligible_generation_failure_alias_binding,
            bound_kind="replacement_eligible_generation_failure_reason",
            challenge_key=challenge_key,
            path=(f"{item_path}/replacement_eligible_generation_failure_alias_binding"),
        )
        if reason.outcome_kind is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
            if not generation_alias.is_bound or not replacement_alias.is_bound:
                raise _invalid(path)
            pins = ("scope_binding", "object_id", "object_version", "content_digest")
            if (
                any(
                    getattr(generation_alias.value, name)
                    != getattr(replacement_alias.value, name)
                    for name in pins
                )
                or generation_alias.value.object_id != reason.reason_id
                or generation_alias.value.object_version != reason.reason_version
                or generation_alias.value.content_digest != reason_ref.content_digest
            ):
                raise _invalid(path, GeneratorInputCode.STALE_BINDING)
        elif (
            generation_alias.is_bound
            or replacement_alias.is_bound
            or generation_alias.value != replacement_alias.value
        ):
            raise _invalid(path)
        fallback_kind = (
            "infrastructure_failure"
            if reason.occurrence_evidence_category
            is FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE
            else "audit_evidence"
        )
        fallback = _owner(
            item.occurrence_evidence_fallback,
            fallback_kind,
            f"{item_path}/occurrence_evidence_fallback",
            challenge_key=challenge_key,
        )
        reconstructed.append(
            GeneratorFailureCatalogEntry(
                reason,
                reason_ref,
                generation_alias,
                replacement_alias,
                fallback,
            )
        )
    return tuple(reconstructed)


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorRequestIdentity:
    challenge_key: ChallengeKey
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    dependency_refs: tuple[object, ...]
    loaded_dependencies: tuple[LoadedDependencyIdentity, ...]
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    intended_unit_link_decision_ref: GeneratorRuntimeRef
    attempt_ref: object
    attempt_ordinal: int
    current_attempt_predecessor_ref: GeneratorRuntimeRef | None
    current_attempt_lineage_ref: object | None
    attempt_accounting_fallback: AttemptAccountingFallback
    attempt_accounting_applicability_reasons: tuple[NamedApplicabilityReason, ...]
    result_applicability_reasons: tuple[NamedApplicabilityReason, ...]
    conformance_fallbacks: tuple[NamedConformanceFallback, ...]
    source_payload_inapplicable_reason_ref: object
    failure_reason_catalog: tuple[GeneratorFailureCatalogEntry, ...]
    disposition_construction: DispositionConstructionBinding
    case_construction: CaseConstructionBinding
    fixture_loading: FixtureLoadingBinding

    def __post_init__(self) -> None:
        if type(self) is not GeneratorRequestIdentity:
            raise _invalid("/request_identity", GeneratorInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        for name, expected in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
        ):
            object.__setattr__(
                self,
                name,
                _reconstruct_top_ref(
                    getattr(self, name),
                    expected,
                    f"/{name}",
                    challenge_key=challenge,
                ),
            )
        raw_dependencies = _exact_tuple(
            self.dependency_refs,
            None,
            "/dependency_refs",
        )
        deps = tuple(
            _reconstruct_any_top_ref(item, f"/dependency_refs/{index}")
            for index, item in enumerate(raw_dependencies)
        )
        if any(item.challenge_key != challenge for item in deps):
            raise _invalid("/dependency_refs", GeneratorInputCode.CROSS_CHALLENGE)
        if len(set(deps)) != len(deps):
            raise _invalid("/dependency_refs")
        deps = tuple(
            sorted(
                deps,
                key=lambda item: encode_value(top_level_ref_to_canonical(item)),
            )
        )
        object.__setattr__(self, "dependency_refs", deps)
        raw_loaded_dependencies = _exact_tuple(
            self.loaded_dependencies,
            LoadedDependencyIdentity,
            "/loaded_dependencies",
        )
        loaded_dependencies: list[LoadedDependencyIdentity] = []
        for index, item in enumerate(raw_loaded_dependencies):
            validation_failure: tuple[str, str] | None = None
            try:
                loaded = replace(item)
            except GeneratorValidationError as error:
                validation_failure = (error.code, error.path)
                loaded = None
            except (AttributeError, AuthoringError, TypeError, ValueError):
                validation_failure = (
                    GeneratorInputCode.INVALID_VALUE.value,
                    f"/loaded_dependencies/{index}",
                )
                loaded = None
            if validation_failure is not None:
                raise GeneratorValidationError(
                    validation_failure[0],
                    path=validation_failure[1],
                )
            if loaded is None:
                raise _invalid(f"/loaded_dependencies/{index}")
            loaded_dependencies.append(loaded)
        loaded_values = tuple(loaded_dependencies)
        if len(set(loaded_values)) != len(loaded_values):
            raise _invalid("/loaded_dependencies")
        loaded_by_ref = {item.expected_ref: item for item in loaded_values}
        if len(loaded_by_ref) != len(loaded_values) or set(loaded_by_ref) != set(deps):
            raise _invalid(
                "/loaded_dependencies",
                GeneratorInputCode.STALE_BINDING,
            )
        loaded_tuple = tuple(loaded_by_ref[dependency_ref] for dependency_ref in deps)
        object.__setattr__(
            self,
            "loaded_dependencies",
            loaded_tuple,
        )
        object.__setattr__(
            self,
            "generator_ref",
            _owner(
                self.generator_ref,
                "generator",
                "/generator_ref",
                challenge_key=challenge,
            ),
        )
        object.__setattr__(
            self,
            "environment_ref",
            _reconstruct_runtime_ref(
                self.environment_ref,
                GeneratorEnvironmentRef,
                challenge_key=challenge,
                path="/environment_ref",
            ),
        )
        object.__setattr__(
            self,
            "fixture_configuration_ref",
            _reconstruct_runtime_ref(
                self.fixture_configuration_ref,
                BurgersFixtureConfigurationRef,
                challenge_key=challenge,
                path="/fixture_configuration_ref",
            ),
        )
        original_role_binding = _exact(
            self.role_binding,
            GenerationRoleBinding,
            "/role_binding",
        )
        role_plan_ref = _reconstruct_top_ref(
            original_role_binding.sampling_plan_ref,
            SamplingPlanRef,
            "/role_binding/sampling_plan_ref",
            challenge_key=challenge,
        )
        role_binding = replace(
            original_role_binding,
            sampling_plan_ref=role_plan_ref,
        )
        if role_binding.sampling_plan_ref != self.sampling_plan_ref:
            raise _invalid(
                "/role_binding/sampling_plan_ref",
                GeneratorInputCode.STALE_BINDING,
            )
        if self.role_binding.sampling_plan_ref != self.sampling_plan_ref:
            raise _invalid("/role_binding", GeneratorInputCode.STALE_BINDING)
        object.__setattr__(self, "role_binding", role_binding)
        object.__setattr__(
            self,
            "replay_ref",
            _reconstruct_replay_ref(
                self.replay_ref,
                challenge_key=challenge,
            ),
        )
        for name, kind in (
            ("intended_slot_ref", "protected_intended_slot"),
            ("intended_evidence_unit_ref", "protected_intended_evidence_unit"),
            ("attempt_ref", "protected_attempt_commitment"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(getattr(self, name), kind, f"/{name}", challenge_key=challenge),
            )
        object.__setattr__(
            self,
            "intended_unit_link_decision_ref",
            _reconstruct_runtime_ref(
                self.intended_unit_link_decision_ref,
                IntendedUnitLinkDecisionRef,
                challenge_key=challenge,
                path="/intended_unit_link_decision_ref",
            ),
        )
        object.__setattr__(
            self, "attempt_ordinal", _uint64(self.attempt_ordinal, "/attempt_ordinal")
        )
        if self.current_attempt_predecessor_ref is not None:
            object.__setattr__(
                self,
                "current_attempt_predecessor_ref",
                _reconstruct_runtime_ref(
                    self.current_attempt_predecessor_ref,
                    PendingGenerationAttemptRef,
                    challenge_key=challenge,
                    path="/current_attempt_predecessor_ref",
                ),
            )
            if self.current_attempt_lineage_ref is None:
                raise _invalid(
                    "/current_attempt_lineage_ref",
                    GeneratorInputCode.INCOMPLETE_BINDING,
                )
        elif self.current_attempt_lineage_ref is not None:
            raise _invalid("/current_attempt_lineage_ref")
        if self.current_attempt_lineage_ref is not None:
            object.__setattr__(
                self,
                "current_attempt_lineage_ref",
                _owner(
                    self.current_attempt_lineage_ref,
                    "protected_replacement_lineage",
                    "/current_attempt_lineage_ref",
                    challenge_key=challenge,
                ),
            )
        object.__setattr__(
            self,
            "attempt_accounting_fallback",
            _reconstruct_nested_record(
                self.attempt_accounting_fallback,
                AttemptAccountingFallback,
                "/attempt_accounting_fallback",
            ),
        )
        for name, expected in (
            (
                "attempt_accounting_applicability_reasons",
                _ATTEMPT_ACCOUNTING_REASON_SCHEMA,
            ),
            ("result_applicability_reasons", _RESULT_REASON_SCHEMA),
        ):
            object.__setattr__(
                self,
                name,
                _reconstruct_named_reasons(
                    getattr(self, name),
                    expected,
                    challenge_key=challenge,
                    path=f"/{name}",
                ),
            )
        conformance_fallbacks = _reconstruct_conformance_fallbacks(
            self.conformance_fallbacks,
            challenge_key=challenge,
        )
        object.__setattr__(
            self,
            "conformance_fallbacks",
            conformance_fallbacks,
        )
        object.__setattr__(
            self,
            "source_payload_inapplicable_reason_ref",
            _owner(
                self.source_payload_inapplicable_reason_ref,
                "applicability_reason",
                "/source_payload_inapplicable_reason_ref",
                challenge_key=challenge,
            ),
        )
        failure_reason_catalog = _reconstruct_failure_catalog(
            self.failure_reason_catalog,
            challenge_key=challenge,
        )
        object.__setattr__(
            self,
            "failure_reason_catalog",
            failure_reason_catalog,
        )
        support_fallback = next(
            entry.occurrence_evidence_fallback
            for entry in failure_reason_catalog
            if entry.reason.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
            and entry.reason.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
        )
        if conformance_fallbacks[-1].fallback_ref != support_fallback:
            raise _invalid(
                "/conformance_fallbacks",
                GeneratorInputCode.STALE_BINDING,
            )
        object.__setattr__(
            self,
            "disposition_construction",
            _reconstruct_nested_record(
                self.disposition_construction,
                DispositionConstructionBinding,
                "/disposition_construction",
            ),
        )
        object.__setattr__(
            self,
            "case_construction",
            _reconstruct_nested_record(
                self.case_construction,
                CaseConstructionBinding,
                "/case_construction",
            ),
        )
        object.__setattr__(
            self,
            "fixture_loading",
            _reconstruct_nested_record(
                self.fixture_loading,
                FixtureLoadingBinding,
                "/fixture_loading",
            ),
        )
        _validate_challenge_scoped_graph(
            self,
            challenge,
            path="/request_identity",
        )

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GeneratorRequestRef:
        from .canonical import _record_ref

        return _record_ref(self, GeneratorRequestRef)

    def __repr__(self) -> str:
        return "GeneratorRequestIdentity(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator request identities cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorRequest:
    challenge_key: ChallengeKey
    authoring_bundle: ResolvedGeneratorAuthoringBundle
    generator: GeneratorDescriptor
    generator_ref: object
    environment: GeneratorEnvironmentDescriptor
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration: object
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    intended_unit_link_decision: object
    intended_unit_link_decision_ref: GeneratorRuntimeRef
    attempt_ref: object
    attempt_ordinal: int
    current_attempt_predecessor_binding: RecordRefPair | None
    current_attempt_lineage_binding: object | None
    attempt_accounting_fallback: AttemptAccountingFallback
    attempt_accounting_applicability_reasons: tuple[NamedApplicabilityReason, ...]
    result_applicability_reasons: tuple[NamedApplicabilityReason, ...]
    conformance_fallbacks: tuple[NamedConformanceFallback, ...]
    source_payload_inapplicable_reason_ref: object
    failure_reason_catalog: tuple[GeneratorFailureCatalogEntry, ...]
    disposition_construction: DispositionConstructionBinding
    case_construction: CaseConstructionBinding
    fixture_loading: FixtureLoadingBinding

    def __post_init__(self) -> None:
        if type(self) is not GeneratorRequest:
            raise _invalid("/request", GeneratorInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        _exact(
            self.authoring_bundle, ResolvedGeneratorAuthoringBundle, "/authoring_bundle"
        )
        _exact(self.generator, GeneratorDescriptor, "/generator")
        if (
            self.authoring_bundle.challenge_key != challenge
            or self.generator.challenge_key != challenge
        ):
            raise _invalid("/challenge_key", GeneratorInputCode.CROSS_CHALLENGE)
        if self.generator.to_ref() != self.generator_ref:
            raise _invalid("/generator_ref", GeneratorInputCode.STALE_BINDING)
        _exact(self.environment, GeneratorEnvironmentDescriptor, "/environment")
        if self.environment.to_ref() != self.environment_ref:
            raise _invalid("/environment_ref", GeneratorInputCode.STALE_BINDING)
        object.__setattr__(
            self,
            "role_binding",
            _reconstruct_nested_record(
                self.role_binding,
                GenerationRoleBinding,
                "/role_binding",
            ),
        )
        object.__setattr__(
            self,
            "replay_ref",
            _reconstruct_replay_ref(
                self.replay_ref,
                challenge_key=challenge,
            ),
        )
        object.__setattr__(
            self,
            "attempt_ordinal",
            _uint64(self.attempt_ordinal, "/attempt_ordinal"),
        )
        object.__setattr__(
            self,
            "attempt_accounting_fallback",
            _reconstruct_nested_record(
                self.attempt_accounting_fallback,
                AttemptAccountingFallback,
                "/attempt_accounting_fallback",
            ),
        )
        if self.current_attempt_predecessor_binding is not None:
            _exact(
                self.current_attempt_predecessor_binding,
                RecordRefPair,
                "/current_attempt_predecessor_binding",
            )
        for name in (
            "attempt_accounting_applicability_reasons",
            "result_applicability_reasons",
            "conformance_fallbacks",
            "failure_reason_catalog",
        ):
            _exact_tuple(getattr(self, name), None, f"/{name}", nonempty=True)
        for name, expected in (
            ("disposition_construction", DispositionConstructionBinding),
            ("case_construction", CaseConstructionBinding),
            ("fixture_loading", FixtureLoadingBinding),
        ):
            object.__setattr__(
                self,
                name,
                _reconstruct_nested_record(
                    getattr(self, name),
                    expected,
                    f"/{name}",
                ),
            )

    def identity(self) -> GeneratorRequestIdentity:
        predecessor_ref = (
            None
            if self.current_attempt_predecessor_binding is None
            else self.current_attempt_predecessor_binding.ref
        )
        return GeneratorRequestIdentity(
            challenge_key=self.challenge_key,
            physical_system_ref=self.authoring_bundle.physical_system_ref,
            candidate_output_ref=self.authoring_bundle.candidate_output_ref,
            primary_population_ref=self.authoring_bundle.primary_population_ref,
            selection_population_ref=self.authoring_bundle.selection_population_ref,
            sampling_plan_ref=self.authoring_bundle.sampling_plan_ref,
            dependency_refs=tuple(
                ref for ref, _ in self.authoring_bundle.resolved_dependencies
            ),
            loaded_dependencies=tuple(
                LoadedDependencyIdentity.from_loaded(item)
                for item in self.authoring_bundle.loaded_dependencies
            ),
            generator_ref=self.generator_ref,
            environment_ref=self.environment_ref,
            fixture_configuration_ref=self.fixture_configuration_ref,
            role_binding=self.role_binding,
            replay_ref=self.replay_ref,
            intended_slot_ref=self.intended_slot_ref,
            intended_evidence_unit_ref=self.intended_evidence_unit_ref,
            intended_unit_link_decision_ref=self.intended_unit_link_decision_ref,
            attempt_ref=self.attempt_ref,
            attempt_ordinal=self.attempt_ordinal,
            current_attempt_predecessor_ref=predecessor_ref,
            current_attempt_lineage_ref=self.current_attempt_lineage_binding,
            attempt_accounting_fallback=self.attempt_accounting_fallback,
            attempt_accounting_applicability_reasons=self.attempt_accounting_applicability_reasons,
            result_applicability_reasons=self.result_applicability_reasons,
            conformance_fallbacks=self.conformance_fallbacks,
            source_payload_inapplicable_reason_ref=self.source_payload_inapplicable_reason_ref,
            failure_reason_catalog=self.failure_reason_catalog,
            disposition_construction=self.disposition_construction,
            case_construction=self.case_construction,
            fixture_loading=self.fixture_loading,
        )

    def to_ref(self) -> GeneratorRequestRef:
        return self.identity().to_ref()

    def __reduce__(self):
        raise TypeError("protected generator requests cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GenerationSourceEvent:
    challenge_key: ChallengeKey
    request_ref: GeneratorRequestRef
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    attempt_ref: object
    payload_ref_binding: ApplicabilityBinding[object]
    materialization_state: SourceMaterializationState

    def __post_init__(self) -> None:
        if type(self) is not GenerationSourceEvent:
            raise _invalid("/source_event", GeneratorInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        _generator_domain_ref(
            self.request_ref, GeneratorRequestRef, "/request_ref", challenge
        )
        for name, expected in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
        ):
            _top(getattr(self, name), expected, f"/{name}", challenge)
        object.__setattr__(
            self,
            "generator_ref",
            _owner(
                self.generator_ref,
                "generator",
                "/generator_ref",
                challenge_key=challenge,
            ),
        )
        _generator_domain_ref(
            self.environment_ref, GeneratorEnvironmentRef, "/environment_ref", challenge
        )
        _generator_domain_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            "/fixture_configuration_ref",
            challenge,
        )
        role_binding = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        _top(
            role_binding.sampling_plan_ref,
            SamplingPlanRef,
            "/role_binding/sampling_plan_ref",
            challenge,
        )
        if role_binding.sampling_plan_ref != self.sampling_plan_ref:
            raise _invalid(
                "/role_binding/sampling_plan_ref",
                GeneratorInputCode.STALE_BINDING,
            )
        object.__setattr__(
            self,
            "fixture_registration_ref",
            _owner(
                self.fixture_registration_ref,
                "fixture_registration",
                "/fixture_registration_ref",
                challenge_key=challenge,
            ),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_tuple(
                self.source_provenance_refs,
                "provenance",
                "/source_provenance_refs",
                challenge_key=challenge,
                nonempty=True,
            ),
        )
        _generator_domain_ref(
            self.replay_ref,
            GeneratorReplayCommitmentRef,
            "/replay_ref",
            challenge,
        )
        for name, kind in (
            ("intended_slot_ref", "protected_intended_slot"),
            ("intended_evidence_unit_ref", "protected_intended_evidence_unit"),
            ("attempt_ref", "protected_attempt_commitment"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(getattr(self, name), kind, f"/{name}", challenge_key=challenge),
            )
        binding = _exact(
            self.payload_ref_binding, ApplicabilityBinding, "/payload_ref_binding"
        )
        if binding.tag is ApplicabilityTag.BOUND:
            _owner(
                binding.value,
                "protected_case_payload",
                "/payload_ref_binding",
                challenge_key=challenge,
            )
        else:
            _owner(
                binding.value,
                "applicability_reason",
                "/payload_ref_binding",
                challenge_key=challenge,
            )
        _exact_enum(
            self.materialization_state,
            SourceMaterializationState,
            "/materialization_state",
        )
        if (
            self.materialization_state is SourceMaterializationState.PAYLOAD_AVAILABLE
        ) != binding.is_bound:
            raise _invalid("/payload_ref_binding")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> object:
        from carbon.authoring.refs import owner_ref

        from .canonical import canonical_content_digest

        return owner_ref(
            "generation_event",
            scope_binding=ChallengeScope(self.challenge_key),
            object_id=self.attempt_ref.object_id,
            object_version=self.attempt_ref.object_version,
            content_digest=canonical_content_digest(self),
        )

    def __repr__(self) -> str:
        return "GenerationSourceEvent(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generation source events cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class TerminalReasonNotApplicable:
    reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not TerminalReasonNotApplicable:
            raise _invalid("/terminal_reason", GeneratorInputCode.WRONG_TYPE)
        object.__setattr__(
            self,
            "reason_ref",
            _owner(self.reason_ref, "applicability_reason", "/reason_ref"),
        )

    def __repr__(self) -> str:
        return "TerminalReasonNotApplicable(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected terminal reasons cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class TerminalReasonSupportDecision:
    support_decision: object
    support_decision_ref: GeneratorRuntimeRef

    def __post_init__(self) -> None:
        if type(self) is not TerminalReasonSupportDecision:
            raise _invalid("/terminal_reason", GeneratorInputCode.WRONG_TYPE)

    def __repr__(self) -> str:
        return "TerminalReasonSupportDecision(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected terminal reasons cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class TerminalReasonCensoringDecision:
    censoring_decision: object
    censoring_decision_ref: GeneratorRuntimeRef
    censoring_record: object
    censoring_record_ref: object

    def __post_init__(self) -> None:
        if type(self) is not TerminalReasonCensoringDecision:
            raise _invalid("/terminal_reason", GeneratorInputCode.WRONG_TYPE)

    def __repr__(self) -> str:
        return "TerminalReasonCensoringDecision(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected terminal reasons cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class TerminalReasonFailure:
    reason: GeneratorFailureReason
    reason_ref: GeneratorFailureReasonRef
    occurrence: GeneratorFailureOccurrence
    occurrence_ref: GeneratorFailureOccurrenceRef

    def __post_init__(self) -> None:
        if type(self) is not TerminalReasonFailure:
            raise _invalid("/terminal_reason", GeneratorInputCode.WRONG_TYPE)
        reason = replace(_exact(self.reason, GeneratorFailureReason, "/reason"))
        reason_ref = _generator_domain_ref(
            self.reason_ref,
            GeneratorFailureReasonRef,
            "/reason_ref",
            reason.challenge_key,
        )
        occurrence = replace(
            _exact(
                self.occurrence,
                GeneratorFailureOccurrence,
                "/occurrence",
            )
        )
        occurrence_ref = _generator_domain_ref(
            self.occurrence_ref,
            GeneratorFailureOccurrenceRef,
            "/occurrence_ref",
            reason.challenge_key,
        )
        if (
            reason.to_ref() != reason_ref
            or occurrence.to_ref() != occurrence_ref
            or occurrence.reason != reason
            or occurrence.reason_ref != reason_ref
        ):
            raise _invalid("/terminal_reason", GeneratorInputCode.STALE_BINDING)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "reason_ref", reason_ref)
        object.__setattr__(self, "occurrence", occurrence)
        object.__setattr__(self, "occurrence_ref", occurrence_ref)

    def __repr__(self) -> str:
        return "TerminalReasonFailure(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected terminal reasons cannot be pickled")


_RESULT_OUTCOME_STAGE_MATRIX = {
    GeneratorOutcomeKind.VALID_GENERATED: frozenset(
        {GeneratorTerminalStage.CENSORING_COMPLETION}
    ),
    GeneratorOutcomeKind.REGISTERED_EXCLUSION: frozenset(
        {GeneratorTerminalStage.SUPPORT_AUTHORITY}
    ),
    GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE: frozenset(
        {
            GeneratorTerminalStage.MATERIALIZATION,
            GeneratorTerminalStage.SUPPORT_AUTHORITY,
        }
    ),
    GeneratorOutcomeKind.INVALID_CONSTRUCTION: frozenset(
        {
            GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY,
            GeneratorTerminalStage.CASE_CONSTRUCTION,
            GeneratorTerminalStage.GRAPH_VALIDATION,
        }
    ),
    GeneratorOutcomeKind.CENSORED_CASE: frozenset(
        {GeneratorTerminalStage.CENSORING_COMPLETION}
    ),
    GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE: frozenset(
        {
            GeneratorTerminalStage.CONTEXT_ACQUISITION,
            GeneratorTerminalStage.DERIVATION,
            GeneratorTerminalStage.MATERIALIZATION,
            GeneratorTerminalStage.SUPPORT_AUTHORITY,
            GeneratorTerminalStage.CASE_CONSTRUCTION,
            GeneratorTerminalStage.CENSORING_AUTHORITY,
            GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
            GeneratorTerminalStage.GRAPH_VALIDATION,
        }
    ),
}


def _result_reason_ref(
    identity: GeneratorRequestIdentity,
    kind: ApplicabilityReasonKind,
) -> object:
    matches = tuple(
        item.reason_ref
        for item in identity.result_applicability_reasons
        if item.kind is kind
    )
    if len(matches) != 1:
        raise _invalid("/request_ref", GeneratorInputCode.STALE_BINDING)
    return matches[0]


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorResultRecord:
    challenge_key: ChallengeKey
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    request_ref: GeneratorRequestRef
    source_event: GenerationSourceEvent
    source_event_ref: object
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    case_binding: RecordRefBinding
    constructed_case_binding: RecordRefBinding
    support_decision_binding: RecordRefBinding
    censoring_verdict_binding: RecordRefBinding
    censoring_decision_binding: RecordRefBinding
    disposition_binding: RecordRefBinding
    terminal_reason_binding: object
    attempt_accounting_decision: object
    attempt_accounting_decision_ref: GeneratorRuntimeRef
    attempt_record: object
    attempt_record_ref: GeneratorRuntimeRef
    conformance_facts: object
    conformance_facts_ref: GeneratorRuntimeRef

    def __post_init__(self) -> None:
        if type(self) is not GeneratorResultRecord:
            raise _invalid("/result_record", GeneratorInputCode.WRONG_TYPE)
        from carbon.authoring.cases import CanonicalChallengeCase
        from carbon.authoring.evidence import (
            CanonicalCaseDisposition,
            CanonicalCaseDispositionRef,
        )
        from carbon.authoring.model import CaseState

        from .accounting import AttemptAccountingDecision, GenerationAttemptRecord
        from .authorities import (
            CensoringDecision,
            CensoringVerdict,
            CensoringVerdictKind,
            PopulationSupportDecisionKind,
            SupportExclusionDecision,
        )
        from .conformance import GeneratorConformanceFacts
        from .refs import (
            AttemptAccountingDecisionRef,
            CensoringDecisionRef,
            CensoringVerdictRef,
            GenerationAttemptRecordRef,
            GeneratorConformanceFactsRef,
            SupportExclusionDecisionRef,
        )

        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        outcome = _exact_enum(
            self.outcome_kind,
            GeneratorOutcomeKind,
            "/outcome_kind",
        )
        stage = _exact_enum(
            self.terminal_stage,
            GeneratorTerminalStage,
            "/terminal_stage",
        )
        if stage not in _RESULT_OUTCOME_STAGE_MATRIX[outcome]:
            raise _invalid("/terminal_stage")

        for name, expected in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
        ):
            _top(getattr(self, name), expected, f"/{name}", challenge)
        object.__setattr__(
            self,
            "generator_ref",
            _owner(
                self.generator_ref,
                "generator",
                "/generator_ref",
                challenge_key=challenge,
            ),
        )
        _generator_domain_ref(
            self.environment_ref,
            GeneratorEnvironmentRef,
            "/environment_ref",
            challenge,
        )
        _generator_domain_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            "/fixture_configuration_ref",
            challenge,
        )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        if role.sampling_plan_ref != self.sampling_plan_ref:
            raise _invalid("/role_binding", GeneratorInputCode.STALE_BINDING)
        object.__setattr__(
            self,
            "fixture_registration_ref",
            _owner(
                self.fixture_registration_ref,
                "fixture_registration",
                "/fixture_registration_ref",
                challenge_key=challenge,
            ),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_tuple(
                self.source_provenance_refs,
                "provenance",
                "/source_provenance_refs",
                challenge_key=challenge,
                nonempty=True,
            ),
        )
        _generator_domain_ref(
            self.request_ref,
            GeneratorRequestRef,
            "/request_ref",
            challenge,
        )
        for name in (
            "case_binding",
            "constructed_case_binding",
            "support_decision_binding",
            "censoring_verdict_binding",
            "censoring_decision_binding",
            "disposition_binding",
        ):
            _exact(getattr(self, name), RecordRefBinding, f"/{name}")
        source_event = _exact(
            self.source_event,
            GenerationSourceEvent,
            "/source_event",
        )
        source_event_ref = _owner(
            self.source_event_ref,
            "generation_event",
            "/source_event_ref",
            challenge_key=challenge,
        )
        object.__setattr__(self, "source_event_ref", source_event_ref)
        if source_event.to_ref() != source_event_ref:
            raise _invalid("/source_event_ref", GeneratorInputCode.STALE_BINDING)

        accounting = _exact(
            self.attempt_accounting_decision,
            AttemptAccountingDecision,
            "/attempt_accounting_decision",
        )
        accounting_ref = _generator_domain_ref(
            self.attempt_accounting_decision_ref,
            AttemptAccountingDecisionRef,
            "/attempt_accounting_decision_ref",
            challenge,
        )
        if accounting.to_ref() != accounting_ref:
            raise _invalid(
                "/attempt_accounting_decision_ref",
                GeneratorInputCode.STALE_BINDING,
            )
        attempt = _exact(
            self.attempt_record,
            GenerationAttemptRecord,
            "/attempt_record",
        )
        attempt_ref = _generator_domain_ref(
            self.attempt_record_ref,
            GenerationAttemptRecordRef,
            "/attempt_record_ref",
            challenge,
        )
        if attempt.to_ref() != attempt_ref:
            raise _invalid("/attempt_record_ref", GeneratorInputCode.STALE_BINDING)
        conformance = _exact(
            self.conformance_facts,
            GeneratorConformanceFacts,
            "/conformance_facts",
        )
        conformance_ref = _generator_domain_ref(
            self.conformance_facts_ref,
            GeneratorConformanceFactsRef,
            "/conformance_facts_ref",
            challenge,
        )
        if conformance.to_ref() != conformance_ref:
            raise _invalid(
                "/conformance_facts_ref",
                GeneratorInputCode.STALE_BINDING,
            )

        directive = accounting.accounting_directive_pair.record
        accounting_request = directive.request
        identity = accounting_request.request_identity
        if (
            identity != conformance.request_identity
            or identity.to_ref() != self.request_ref
            or accounting_request.request_ref != self.request_ref
            or accounting_request.source_event != source_event
            or accounting_request.source_event_ref != source_event_ref
            or conformance.request_ref != self.request_ref
            or conformance.source_event != source_event
            or conformance.source_event_ref != source_event_ref
        ):
            raise _invalid("/request_ref", GeneratorInputCode.STALE_BINDING)

        echoed_fields = (
            "physical_system_ref",
            "candidate_output_ref",
            "primary_population_ref",
            "selection_population_ref",
            "sampling_plan_ref",
            "generator_ref",
            "environment_ref",
            "fixture_configuration_ref",
            "role_binding",
        )
        if any(
            getattr(self, name) != getattr(identity, name)
            or getattr(self, name) != getattr(source_event, name)
            for name in echoed_fields
        ) or any(
            getattr(self, name) != getattr(conformance, name)
            for name in (
                "primary_population_ref",
                "selection_population_ref",
                "sampling_plan_ref",
                "generator_ref",
                "environment_ref",
                "fixture_configuration_ref",
                "role_binding",
            )
        ):
            raise _invalid("/request_ref", GeneratorInputCode.STALE_BINDING)
        if (
            self.fixture_registration_ref != source_event.fixture_registration_ref
            or self.source_provenance_refs != source_event.source_provenance_refs
            or source_event.replay_ref != identity.replay_ref
            or source_event.intended_slot_ref != identity.intended_slot_ref
            or source_event.intended_evidence_unit_ref
            != identity.intended_evidence_unit_ref
            or source_event.attempt_ref != identity.attempt_ref
        ):
            raise _invalid("/source_event", GeneratorInputCode.STALE_BINDING)

        if (
            accounting.challenge_key != challenge
            or accounting.request_ref != self.request_ref
            or accounting.source_event_ref != source_event_ref
            or accounting.final_outcome is not outcome
            or accounting.final_stage is not stage
            or attempt.challenge_key != challenge
            or attempt.request_ref != self.request_ref
            or attempt.source_event_ref != source_event_ref
            or attempt.outcome_kind is not outcome
            or attempt.terminal_stage is not stage
            or attempt.materialization_state is not source_event.materialization_state
            or conformance.challenge_key != challenge
            or conformance.outcome_kind is not outcome
            or conformance.terminal_stage is not stage
        ):
            raise _invalid("/terminal_stage", GeneratorInputCode.STALE_BINDING)
        if (
            attempt.accounting_decision_pair.record != accounting
            or attempt.accounting_decision_pair.ref != accounting_ref
            or attempt.conformance_facts_pair.record != conformance
            or attempt.conformance_facts_pair.ref != conformance_ref
        ):
            raise _invalid("/attempt_record", GeneratorInputCode.STALE_BINDING)
        for name in (
            "generator_ref",
            "environment_ref",
            "fixture_configuration_ref",
            "primary_population_ref",
            "selection_population_ref",
            "sampling_plan_ref",
            "role_binding",
        ):
            if getattr(attempt, name) != getattr(self, name):
                raise _invalid("/attempt_record", GeneratorInputCode.STALE_BINDING)
        for name in (
            "replay_ref",
            "intended_slot_ref",
            "intended_evidence_unit_ref",
            "attempt_ref",
            "attempt_ordinal",
        ):
            if getattr(attempt, name) != getattr(identity, name):
                raise _invalid("/attempt_record", GeneratorInputCode.STALE_BINDING)

        def require_bound_pair(
            binding: RecordRefBinding,
            record_type: type,
            ref_type: type,
            path: str,
        ) -> RecordRefPair:
            pair = _exact(binding.pair, RecordRefPair, f"{path}/pair")
            if type(pair.record) is not record_type or type(pair.ref) is not ref_type:
                raise _invalid(path, GeneratorInputCode.WRONG_TYPE)
            return pair

        case_required = outcome in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.CENSORED_CASE,
        }
        if self.case_binding.is_bound != case_required:
            raise _invalid("/case_binding")
        if self.case_binding.is_bound:
            case_pair = require_bound_pair(
                self.case_binding,
                CanonicalChallengeCase,
                CanonicalChallengeCaseRef,
                "/case_binding",
            )
            if (
                not self.constructed_case_binding.is_bound
                or self.constructed_case_binding.pair != case_pair
            ):
                raise _invalid("/constructed_case_binding")
        elif self.case_binding.reason_ref != _result_reason_ref(
            identity,
            ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
        ):
            raise _invalid("/case_binding", GeneratorInputCode.STALE_BINDING)

        if self.constructed_case_binding != accounting_request.constructed_case_binding:
            raise _invalid(
                "/constructed_case_binding",
                GeneratorInputCode.STALE_BINDING,
            )
        if self.constructed_case_binding.is_bound:
            constructed_pair = require_bound_pair(
                self.constructed_case_binding,
                CanonicalChallengeCase,
                CanonicalChallengeCaseRef,
                "/constructed_case_binding",
            )
            if not case_required and not (
                outcome is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
                and stage
                in {
                    GeneratorTerminalStage.CENSORING_AUTHORITY,
                    GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
                }
            ):
                raise _invalid("/constructed_case_binding")
            validated_case = conformance.validated_case_facts_binding
            if (
                not validated_case.is_bound
                or validated_case.value.case_ref != constructed_pair.ref
            ):
                raise _invalid(
                    "/constructed_case_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        else:
            if self.constructed_case_binding.reason_ref != _result_reason_ref(
                identity,
                ApplicabilityReasonKind.CONSTRUCTED_CASE_INAPPLICABLE,
            ):
                raise _invalid(
                    "/constructed_case_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
            if conformance.validated_case_facts_binding.is_bound:
                raise _invalid(
                    "/constructed_case_binding",
                    GeneratorInputCode.STALE_BINDING,
                )

        binding_types = (
            (
                "support_decision_binding",
                SupportExclusionDecision,
                SupportExclusionDecisionRef,
                ApplicabilityReasonKind.SUPPORT_DECISION_INAPPLICABLE,
            ),
            (
                "censoring_verdict_binding",
                CensoringVerdict,
                CensoringVerdictRef,
                ApplicabilityReasonKind.CENSORING_VERDICT_INAPPLICABLE,
            ),
            (
                "censoring_decision_binding",
                CensoringDecision,
                CensoringDecisionRef,
                ApplicabilityReasonKind.CENSORING_DECISION_INAPPLICABLE,
            ),
        )
        for name, record_type, ref_type, reason_kind in binding_types:
            binding = getattr(self, name)
            if binding.is_bound:
                require_bound_pair(binding, record_type, ref_type, f"/{name}")
            elif binding.reason_ref != _result_reason_ref(identity, reason_kind):
                raise _invalid(f"/{name}", GeneratorInputCode.STALE_BINDING)
        if (
            self.support_decision_binding != accounting_request.support_decision_binding
            or self.support_decision_binding != attempt.support_decision_binding
            or self.censoring_verdict_binding
            != accounting_request.censoring_verdict_binding
            or self.censoring_verdict_binding != attempt.censoring_verdict_binding
            or self.censoring_decision_binding != attempt.censoring_decision_binding
            or self.support_decision_binding.is_bound
            != conformance.support_decision_binding.is_bound
            or (
                self.support_decision_binding.is_bound
                and self.support_decision_binding
                != conformance.support_decision_binding
            )
        ):
            raise _invalid(
                "/support_decision_binding",
                GeneratorInputCode.STALE_BINDING,
            )

        if self.support_decision_binding.is_bound:
            support = self.support_decision_binding.pair.record
            if outcome is GeneratorOutcomeKind.REGISTERED_EXCLUSION and (
                support.terminal_resolution
                is not PopulationSupportDecisionKind.REGISTERED_EXCLUSION
            ):
                raise _invalid(
                    "/support_decision_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
            if (
                outcome is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE
                and stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
                and support.terminal_resolution
                is not PopulationSupportDecisionKind.OUTSIDE_REGISTERED_SUPPORT
            ):
                raise _invalid(
                    "/support_decision_binding",
                    GeneratorInputCode.STALE_BINDING,
                )

        if case_required:
            if not self.censoring_verdict_binding.is_bound:
                raise _invalid("/censoring_verdict_binding")
            verdict_kind = self.censoring_verdict_binding.pair.record.verdict_kind
            expected_verdict = (
                CensoringVerdictKind.CENSORED
                if outcome is GeneratorOutcomeKind.CENSORED_CASE
                else CensoringVerdictKind.NOT_CENSORED
            )
            if verdict_kind is not expected_verdict:
                raise _invalid(
                    "/censoring_verdict_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        if self.censoring_decision_binding.is_bound:
            censoring_decision = self.censoring_decision_binding.pair.record
            if (
                not self.censoring_verdict_binding.is_bound
                or censoring_decision.verdict
                != self.censoring_verdict_binding.pair.record
                or censoring_decision.verdict_ref
                != self.censoring_verdict_binding.pair.ref
                or censoring_decision.accounting_decision != accounting
                or censoring_decision.accounting_decision_ref != accounting_ref
            ):
                raise _invalid(
                    "/censoring_decision_binding",
                    GeneratorInputCode.STALE_BINDING,
                )

        if attempt.case_ref_binding.is_bound != case_required:
            raise _invalid("/case_binding", GeneratorInputCode.STALE_BINDING)
        if case_required:
            if attempt.case_ref_binding.value != self.case_binding.pair.ref:
                raise _invalid("/case_binding", GeneratorInputCode.STALE_BINDING)
        elif attempt.case_ref_binding.value != self.case_binding.reason_ref:
            raise _invalid("/case_binding", GeneratorInputCode.STALE_BINDING)

        disposition_required = outcome in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.REGISTERED_EXCLUSION,
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.CENSORED_CASE,
        }
        if self.disposition_binding.is_bound != disposition_required:
            raise _invalid("/disposition_binding")
        if self.disposition_binding.is_bound:
            disposition_pair = require_bound_pair(
                self.disposition_binding,
                CanonicalCaseDisposition,
                CanonicalCaseDispositionRef,
                "/disposition_binding",
            )
            disposition = disposition_pair.record
            expected_state = {
                GeneratorOutcomeKind.VALID_GENERATED: CaseState.VALID,
                GeneratorOutcomeKind.REGISTERED_EXCLUSION: CaseState.EXCLUDED,
                GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE: (
                    CaseState.GENERATION_FAILURE
                ),
                GeneratorOutcomeKind.CENSORED_CASE: CaseState.CENSORED,
            }[outcome]
            if (
                disposition.case_state is not expected_state
                or disposition.intended_evidence_unit_ref
                != identity.intended_evidence_unit_ref
                or disposition.sampling_plan_ref != self.sampling_plan_ref
                or disposition.primary_population_ref != self.primary_population_ref
                or disposition.replacement_decision
                != accounting.outcome_replacement_binding.value
            ):
                raise _invalid(
                    "/disposition_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
            if case_required:
                if (
                    disposition.case_ref_binding.value != self.case_binding.pair.ref
                    or disposition.attempt_commitment_binding.is_bound
                    or disposition.attempt_commitment_binding.value
                    != identity.disposition_construction.attempt_inapplicable_reason_ref
                ):
                    raise _invalid(
                        "/disposition_binding",
                        GeneratorInputCode.STALE_BINDING,
                    )
            elif (
                disposition.case_ref_binding.is_bound
                or disposition.case_ref_binding.value
                != identity.disposition_construction.case_inapplicable_reason_ref
                or not disposition.attempt_commitment_binding.is_bound
                or disposition.attempt_commitment_binding.value != identity.attempt_ref
            ):
                raise _invalid(
                    "/disposition_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        elif self.disposition_binding.reason_ref != _result_reason_ref(
            identity,
            ApplicabilityReasonKind.DISPOSITION_INAPPLICABLE,
        ):
            raise _invalid(
                "/disposition_binding",
                GeneratorInputCode.STALE_BINDING,
            )

        failure_outcome = outcome in {
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        }
        reason = self.terminal_reason_binding
        if outcome is GeneratorOutcomeKind.VALID_GENERATED:
            terminal_reason = _exact(
                reason,
                TerminalReasonNotApplicable,
                "/terminal_reason_binding",
            )
            if terminal_reason.reason_ref != _result_reason_ref(
                identity,
                ApplicabilityReasonKind.TERMINAL_REASON_INAPPLICABLE,
            ):
                raise _invalid(
                    "/terminal_reason_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        elif outcome is GeneratorOutcomeKind.REGISTERED_EXCLUSION:
            terminal_reason = _exact(
                reason,
                TerminalReasonSupportDecision,
                "/terminal_reason_binding",
            )
            if (
                not self.support_decision_binding.is_bound
                or terminal_reason.support_decision
                != self.support_decision_binding.pair.record
                or terminal_reason.support_decision_ref
                != self.support_decision_binding.pair.ref
            ):
                raise _invalid(
                    "/terminal_reason_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        elif outcome is GeneratorOutcomeKind.CENSORED_CASE:
            terminal_reason = _exact(
                reason,
                TerminalReasonCensoringDecision,
                "/terminal_reason_binding",
            )
            if (
                not self.censoring_decision_binding.is_bound
                or terminal_reason.censoring_decision
                != self.censoring_decision_binding.pair.record
                or terminal_reason.censoring_decision_ref
                != self.censoring_decision_binding.pair.ref
                or terminal_reason.censoring_record
                != terminal_reason.censoring_decision.censoring_record
                or terminal_reason.censoring_record_ref
                != terminal_reason.censoring_decision.censoring_record_ref
            ):
                raise _invalid(
                    "/terminal_reason_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
        elif failure_outcome:
            terminal_reason = _exact(
                reason,
                TerminalReasonFailure,
                "/terminal_reason_binding",
            )
            failure_reason_pair = attempt.failure_reason_binding.pair
            failure_occurrence_pair = attempt.failure_occurrence_binding.pair
            catalog_matches = tuple(
                entry
                for entry in identity.failure_reason_catalog
                if entry.reason.outcome_kind is outcome
                and entry.reason.terminal_stage is stage
            )
            if len(catalog_matches) != 1:
                raise _invalid(
                    "/terminal_reason_binding",
                    GeneratorInputCode.STALE_BINDING,
                )
            catalog_entry = catalog_matches[0]
            if (
                failure_reason_pair is None
                or failure_occurrence_pair is None
                or type(terminal_reason.reason) is not GeneratorFailureReason
                or type(terminal_reason.reason_ref) is not GeneratorFailureReasonRef
                or type(terminal_reason.occurrence) is not GeneratorFailureOccurrence
                or type(terminal_reason.occurrence_ref)
                is not GeneratorFailureOccurrenceRef
                or terminal_reason.reason != failure_reason_pair.record
                or terminal_reason.reason_ref != failure_reason_pair.ref
                or terminal_reason.occurrence != failure_occurrence_pair.record
                or terminal_reason.occurrence_ref != failure_occurrence_pair.ref
                or terminal_reason.reason.outcome_kind is not outcome
                or terminal_reason.reason.terminal_stage is not stage
                or terminal_reason.occurrence.request_ref != self.request_ref
                or terminal_reason.occurrence.source_event_ref != source_event_ref
                or terminal_reason.reason != catalog_entry.reason
                or terminal_reason.reason_ref != catalog_entry.reason_ref
                or terminal_reason.occurrence.reason != catalog_entry.reason
                or terminal_reason.occurrence.reason_ref != catalog_entry.reason_ref
                or terminal_reason.occurrence.generation_failure_alias_binding
                != catalog_entry.generation_failure_alias_binding
                or terminal_reason.occurrence.replacement_eligible_generation_failure_alias_binding
                != catalog_entry.replacement_eligible_generation_failure_alias_binding
                or not terminal_reason.occurrence.occurrence_evidence_binding.is_bound
                or terminal_reason.occurrence.occurrence_evidence_binding.value
                != catalog_entry.occurrence_evidence_fallback
            ):
                raise _invalid(
                    "/terminal_reason_binding",
                    GeneratorInputCode.STALE_BINDING,
                )

        _validate_challenge_scoped_graph(
            self,
            challenge,
            path="/result_record",
        )

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GeneratorResultRef:
        from .canonical import _record_ref

        return _record_ref(self, GeneratorResultRef)

    def __repr__(self) -> str:
        return "GeneratorResultRecord(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator result records cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorResult:
    record: GeneratorResultRecord
    ref: GeneratorResultRef
    artifact: object | None

    def __post_init__(self) -> None:
        if type(self) is not GeneratorResult:
            raise _invalid("/result", GeneratorInputCode.WRONG_TYPE)
        record = replace(_exact(self.record, GeneratorResultRecord, "/record"))
        ref = _exact(self.ref, GeneratorResultRef, "/ref")
        if record.to_ref() != ref:
            raise _invalid("/ref", GeneratorInputCode.STALE_BINDING)
        if record.constructed_case_binding.is_bound:
            from .burgers import (
                GeneratedFixtureArtifact,
                build_generated_fixture_artifact,
                build_validated_case_facts,
            )

            artifact = _exact(
                self.artifact,
                GeneratedFixtureArtifact,
                "/artifact",
            )
            checked_artifact = build_generated_fixture_artifact(
                case=artifact.case,
                case_ref=artifact.case_ref,
                loaded_case=artifact.loaded_case,
                loaded_dependencies=artifact.loaded_dependencies,
                graph_origin=artifact.graph_origin,
            )
            pair = record.constructed_case_binding.pair
            if (
                checked_artifact.case != pair.record
                or checked_artifact.case_ref != pair.ref
            ):
                raise _invalid("/artifact", GeneratorInputCode.STALE_BINDING)
            validated_binding = record.conformance_facts.validated_case_facts_binding
            expected_facts = build_validated_case_facts(checked_artifact)
            if (
                not validated_binding.is_bound
                or validated_binding.value != expected_facts
            ):
                raise _invalid("/artifact", GeneratorInputCode.STALE_BINDING)
        else:
            if self.artifact is not None:
                raise _invalid("/artifact")
            checked_artifact = None
        object.__setattr__(self, "record", record)
        object.__setattr__(self, "ref", ref)
        object.__setattr__(self, "artifact", checked_artifact)

    def __reduce__(self):
        raise TypeError("protected generator results cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorInvocationOutput:
    kind: GeneratorInvocationOutputKind
    payload: object

    def __post_init__(self) -> None:
        if type(self) is not GeneratorInvocationOutput:
            raise _invalid("/invocation_output", GeneratorInputCode.WRONG_TYPE)
        _exact_enum(self.kind, GeneratorInvocationOutputKind, "/kind")
        if self.kind is GeneratorInvocationOutputKind.FINAL:
            payload = replace(_exact(self.payload, GeneratorResult, "/payload"))
        else:
            from .accounting import PendingGenerationAttempt

            payload = _exact(
                self.payload,
                PendingGenerationAttempt,
                "/payload",
            )
            payload = replace(payload)
        object.__setattr__(self, "payload", payload)

    @classmethod
    def final(cls, result: GeneratorResult) -> GeneratorInvocationOutput:
        return cls(GeneratorInvocationOutputKind.FINAL, result)

    @classmethod
    def pending_successor(cls, pending: object) -> GeneratorInvocationOutput:
        return cls(GeneratorInvocationOutputKind.PENDING_SUCCESSOR, pending)

    def __reduce__(self):
        raise TypeError("generator invocation outputs cannot be pickled")


# Closed canonical schemas.  Field order here is normative input to the B-03
# codec; CanonicalRecord itself emits canonical UTF-8 lexical field order.
from .canonical import (
    _ANY_GENERATOR_REF,
    _ANY_OWNER_REF,
    _ANY_RECORD,
    _ANY_REF,
    _ANY_TOP_REF,
    _CHALLENGE_KEY,
    _REPLAY_REF,
    _ROLE_KEY,
    _TEXT,
    _UINT64,
    GENERATOR_IMPLEMENTATION_MANIFEST_HEADER,
    _applicability,
    _authoring,
    _closed_union,
    _enum,
    _generator_ref,
    _nested,
    _optional,
    _record,
    _register_canonical_type,
    _register_nested_canonical_type,
    _top_ref,
    _tuple_of,
)
from .canonical import (
    _owner as _owner_codec,
)

_register_nested_canonical_type(
    GenerationRoleBinding,
    record_type="generation_role_binding",
    fields=(
        ("sampling_role", _enum(SamplingRole)),
        ("seed_domain", _enum(SeedDomain)),
        ("role_key", _ROLE_KEY),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
    ),
)
_register_nested_canonical_type(
    LoadedDependencyIdentity,
    record_type="loaded_dependency_identity",
    fields=(
        ("expected_ref", _ANY_TOP_REF),
        ("recomputed_ref", _ANY_TOP_REF),
        ("origin_tag", _enum(OriginTag)),
        ("origin_evidence_ref", _owner_codec("authoring_origin_evidence")),
        (
            "source_provenance_refs",
            _tuple_of(_owner_codec("provenance"), set_like=True),
        ),
        (
            "audit_evidence_refs",
            _tuple_of(_owner_codec("audit_evidence"), set_like=True),
        ),
        (
            "qualification_evidence",
            _applicability(_owner_codec("qualification_evidence_bundle")),
        ),
    ),
)
_register_nested_canonical_type(
    CaseConstructionBinding,
    record_type="case_construction_binding",
    fields=(
        ("object_id", _TEXT),
        ("object_version", _TEXT),
        ("supersedes", _applicability(_top_ref(CanonicalChallengeCaseRef))),
        (
            "related_population_bindings",
            _tuple_of(_authoring(RelatedPopulationBinding)),
        ),
        ("case_representation_ref", _owner_codec("representation")),
        (
            "query_population_binding",
            _applicability(_top_ref(InstanceDistributionContractRef)),
        ),
        (
            "observation_population_binding",
            _applicability(_top_ref(InstanceDistributionContractRef)),
        ),
        (
            "evidence_campaign_binding",
            _applicability(_owner_codec("evidence_campaign")),
        ),
        (
            "intended_slot_binding",
            _applicability(_owner_codec("protected_intended_slot")),
        ),
        (
            "prospective_censoring_policy_binding",
            _applicability(_owner_codec("censoring_policy")),
        ),
        (
            "applicability_bindings",
            _tuple_of(_owner_codec("applicability"), set_like=True),
        ),
        ("disclosure_class", _enum(DisclosureClass)),
        ("disclosure_contract", _authoring(DisclosureContract)),
        ("case_provenance_refs", _tuple_of(_owner_codec("provenance"), set_like=True)),
    ),
)
_register_nested_canonical_type(
    FixtureLoadingBinding,
    record_type="fixture_loading_binding",
    fields=(
        ("origin_evidence_ref", _owner_codec("authoring_origin_evidence")),
        (
            "audit_evidence_refs",
            _tuple_of(_owner_codec("audit_evidence"), set_like=True),
        ),
        ("composition_audit_ref", _owner_codec("origin_composition_audit")),
        ("fixture_unqualified_reason_ref", _owner_codec("applicability_reason")),
    ),
)
_register_nested_canonical_type(
    DispositionConstructionBinding,
    record_type="disposition_construction_binding",
    fields=(
        ("evidence_scope", _authoring(EvidenceScopeBinding)),
        ("policy_authority_ref", _owner_codec("policy_authority")),
        (
            "audit_evidence_refs",
            _tuple_of(_owner_codec("audit_evidence"), set_like=True),
        ),
        (
            "downstream_use_restrictions",
            _tuple_of(_owner_codec("restriction"), set_like=True),
        ),
        ("disclosure_contract", _authoring(DisclosureContract)),
        ("case_inapplicable_reason_ref", _owner_codec("applicability_reason")),
        ("attempt_inapplicable_reason_ref", _owner_codec("applicability_reason")),
    ),
)
_register_nested_canonical_type(
    AttemptAccountingFallback,
    record_type="attempt_accounting_fallback",
    fields=(
        ("authority_failure_ref", _owner_codec("infrastructure_failure")),
        ("denominator_unavailable_reason_ref", _owner_codec("applicability_reason")),
    ),
)
_register_nested_canonical_type(
    NamedApplicabilityReason,
    record_type="named_applicability_reason",
    fields=(
        ("kind", _enum(ApplicabilityReasonKind)),
        ("reason_ref", _owner_codec("applicability_reason")),
    ),
)
_register_nested_canonical_type(
    NamedConformanceFallback,
    record_type="named_conformance_fallback",
    fields=(("fallback_id", _TEXT), ("fallback_ref", _ANY_OWNER_REF)),
)
_register_nested_canonical_type(
    GeneratorFailureCatalogEntry,
    record_type="generator_failure_catalog_entry",
    fields=(
        ("reason", _record(GeneratorFailureReason)),
        ("reason_ref", _generator_ref(GeneratorFailureReasonRef)),
        (
            "generation_failure_alias_binding",
            _applicability(_owner_codec("generation_failure")),
        ),
        (
            "replacement_eligible_generation_failure_alias_binding",
            _applicability(
                _owner_codec("replacement_eligible_generation_failure_reason")
            ),
        ),
        ("occurrence_evidence_fallback", _ANY_OWNER_REF),
    ),
)
_register_nested_canonical_type(
    RecordRefPair,
    record_type="record_ref_pair",
    fields=(("record", _ANY_RECORD), ("ref", _ANY_REF)),
)
_register_nested_canonical_type(
    RecordRefBinding,
    record_type="record_ref_binding",
    fields=(
        ("tag", _enum(RecordRefBindingTag)),
        ("pair", _optional(_nested(RecordRefPair))),
        ("reason_ref", _optional(_owner_codec("applicability_reason"))),
    ),
)
_register_nested_canonical_type(
    TerminalReasonNotApplicable,
    record_type="terminal_reason_not_applicable",
    union_tag="NOT_APPLICABLE",
    fields=(("reason_ref", _owner_codec("applicability_reason")),),
)
_register_nested_canonical_type(
    TerminalReasonSupportDecision,
    record_type="terminal_reason_support_decision",
    union_tag="SUPPORT_DECISION",
    fields=(
        ("support_decision", _ANY_RECORD),
        ("support_decision_ref", _ANY_GENERATOR_REF),
    ),
)
_register_nested_canonical_type(
    TerminalReasonCensoringDecision,
    record_type="terminal_reason_censoring_decision",
    union_tag="CENSORING_DECISION",
    fields=(
        ("censoring_decision", _ANY_RECORD),
        ("censoring_decision_ref", _ANY_GENERATOR_REF),
        ("censoring_record", _ANY_RECORD),
        ("censoring_record_ref", _ANY_REF),
    ),
)
_register_nested_canonical_type(
    TerminalReasonFailure,
    record_type="terminal_reason_failure",
    union_tag="FAILURE",
    fields=(
        ("reason", _record(GeneratorFailureReason)),
        ("reason_ref", _generator_ref(GeneratorFailureReasonRef)),
        ("occurrence", _record(GeneratorFailureOccurrence)),
        ("occurrence_ref", _generator_ref(GeneratorFailureOccurrenceRef)),
    ),
)

_register_canonical_type(
    GeneratorImplementationManifest,
    object_kind="generator_implementation_manifest",
    document_header=GENERATOR_IMPLEMENTATION_MANIFEST_HEADER,
    include_identity_fields=False,
    fields=(
        ("implementation_id", _TEXT),
        ("implementation_version", _TEXT),
        ("package", _TEXT),
        ("runtime_contract_version", _TEXT),
        ("canonical_profile", _TEXT),
        ("fixture_configuration_ref", _generator_ref(BurgersFixtureConfigurationRef)),
        ("latent_codec_id", _TEXT),
    ),
)
_register_canonical_type(
    GeneratorEnvironmentDescriptor,
    object_kind="generator_environment",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("environment_id", _TEXT),
        ("environment_version", _TEXT),
        ("python_implementation", _TEXT),
        ("python_version", _TEXT),
        ("platform_tag", _TEXT),
        ("dependency_lock_digest", _TEXT),
        ("environment_class", _enum(GeneratorEnvironmentClass)),
    ),
)
_register_canonical_type(
    GeneratorDescriptor,
    object_kind="generator_descriptor",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("generator_id", _TEXT),
        ("generator_version", _TEXT),
        ("implementation_digest", _TEXT),
        ("environment_ref", _generator_ref(GeneratorEnvironmentRef)),
        ("fixture_registration_ref", _owner_codec("fixture_registration")),
        (
            "source_provenance_refs",
            _tuple_of(_owner_codec("provenance"), set_like=True),
        ),
        ("fixture_configuration_ref", _generator_ref(BurgersFixtureConfigurationRef)),
        ("supported_physical_system_ref", _top_ref(PhysicalSystemSpecRef)),
        ("supported_candidate_output_ref", _top_ref(CandidateOutputContractRef)),
        ("supported_primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        (
            "supported_selection_population_ref",
            _top_ref(InstanceDistributionContractRef),
        ),
    ),
)
_register_canonical_type(
    GeneratorFailureReason,
    object_kind="generator_failure_reason",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("reason_id", _TEXT),
        ("reason_version", _TEXT),
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("terminal_stage", _enum(GeneratorTerminalStage)),
        ("reason_code", _TEXT),
        ("occurrence_evidence_category", _enum(FailureOccurrenceEvidenceCategory)),
    ),
)
_register_canonical_type(
    GeneratorFailureOccurrence,
    object_kind="generator_failure_occurrence",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_ref", _generator_ref(GeneratorRequestRef)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("reason", _record(GeneratorFailureReason)),
        ("reason_ref", _generator_ref(GeneratorFailureReasonRef)),
        (
            "generation_failure_alias_binding",
            _applicability(_owner_codec("generation_failure")),
        ),
        (
            "replacement_eligible_generation_failure_alias_binding",
            _applicability(
                _owner_codec("replacement_eligible_generation_failure_reason")
            ),
        ),
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("terminal_stage", _enum(GeneratorTerminalStage)),
        ("occurrence_evidence_binding", _applicability(_ANY_OWNER_REF)),
    ),
)
_register_canonical_type(
    GeneratorRequestIdentity,
    object_kind="generator_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("physical_system_ref", _top_ref(PhysicalSystemSpecRef)),
        ("candidate_output_ref", _top_ref(CandidateOutputContractRef)),
        ("primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("selection_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        ("dependency_refs", _tuple_of(_ANY_TOP_REF, set_like=True)),
        ("loaded_dependencies", _tuple_of(_nested(LoadedDependencyIdentity))),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref(GeneratorEnvironmentRef)),
        ("fixture_configuration_ref", _generator_ref(BurgersFixtureConfigurationRef)),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("replay_ref", _REPLAY_REF),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("intended_unit_link_decision_ref", _ANY_GENERATOR_REF),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
        ("attempt_ordinal", _UINT64),
        ("current_attempt_predecessor_ref", _optional(_ANY_GENERATOR_REF)),
        (
            "current_attempt_lineage_ref",
            _optional(_owner_codec("protected_replacement_lineage")),
        ),
        ("attempt_accounting_fallback", _nested(AttemptAccountingFallback)),
        (
            "attempt_accounting_applicability_reasons",
            _tuple_of(_nested(NamedApplicabilityReason)),
        ),
        ("result_applicability_reasons", _tuple_of(_nested(NamedApplicabilityReason))),
        ("conformance_fallbacks", _tuple_of(_nested(NamedConformanceFallback))),
        (
            "source_payload_inapplicable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        ("failure_reason_catalog", _tuple_of(_nested(GeneratorFailureCatalogEntry))),
        ("disposition_construction", _nested(DispositionConstructionBinding)),
        ("case_construction", _nested(CaseConstructionBinding)),
        ("fixture_loading", _nested(FixtureLoadingBinding)),
    ),
)
_register_canonical_type(
    GenerationSourceEvent,
    object_kind="generation_source_event",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_ref", _generator_ref(GeneratorRequestRef)),
        ("physical_system_ref", _top_ref(PhysicalSystemSpecRef)),
        ("candidate_output_ref", _top_ref(CandidateOutputContractRef)),
        ("primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("selection_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref(GeneratorEnvironmentRef)),
        ("fixture_configuration_ref", _generator_ref(BurgersFixtureConfigurationRef)),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("fixture_registration_ref", _owner_codec("fixture_registration")),
        (
            "source_provenance_refs",
            _tuple_of(_owner_codec("provenance"), set_like=True),
        ),
        ("replay_ref", _REPLAY_REF),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
        ("payload_ref_binding", _applicability(_owner_codec("protected_case_payload"))),
        ("materialization_state", _enum(SourceMaterializationState)),
    ),
)
_register_canonical_type(
    GeneratorResultRecord,
    object_kind="generator_result",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("physical_system_ref", _top_ref(PhysicalSystemSpecRef)),
        ("candidate_output_ref", _top_ref(CandidateOutputContractRef)),
        ("primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("selection_population_ref", _top_ref(InstanceDistributionContractRef)),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref(GeneratorEnvironmentRef)),
        ("fixture_configuration_ref", _generator_ref(BurgersFixtureConfigurationRef)),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("fixture_registration_ref", _owner_codec("fixture_registration")),
        (
            "source_provenance_refs",
            _tuple_of(_owner_codec("provenance"), set_like=True),
        ),
        ("request_ref", _generator_ref(GeneratorRequestRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("terminal_stage", _enum(GeneratorTerminalStage)),
        ("case_binding", _nested(RecordRefBinding)),
        ("constructed_case_binding", _nested(RecordRefBinding)),
        ("support_decision_binding", _nested(RecordRefBinding)),
        ("censoring_verdict_binding", _nested(RecordRefBinding)),
        ("censoring_decision_binding", _nested(RecordRefBinding)),
        ("disposition_binding", _nested(RecordRefBinding)),
        (
            "terminal_reason_binding",
            _closed_union(
                TerminalReasonNotApplicable,
                TerminalReasonSupportDecision,
                TerminalReasonCensoringDecision,
                TerminalReasonFailure,
            ),
        ),
        ("attempt_accounting_decision", _ANY_RECORD),
        ("attempt_accounting_decision_ref", _ANY_GENERATOR_REF),
        ("attempt_record", _ANY_RECORD),
        ("attempt_record_ref", _ANY_GENERATOR_REF),
        ("conformance_facts", _ANY_RECORD),
        ("conformance_facts_ref", _ANY_GENERATOR_REF),
    ),
)


__all__ = [
    "ApplicabilityReasonKind",
    "AttemptAccountingFallback",
    "CaseConstructionBinding",
    "DispositionConstructionBinding",
    "FailureOccurrenceEvidenceCategory",
    "FixtureLoadingBinding",
    "GenerationRoleBinding",
    "GenerationSourceEvent",
    "GeneratorDescriptor",
    "GeneratorEnvironmentClass",
    "GeneratorEnvironmentDescriptor",
    "GeneratorFailureCatalogEntry",
    "GeneratorFailureOccurrence",
    "GeneratorFailureReason",
    "GeneratorImplementationManifest",
    "GeneratorInvocationOutput",
    "GeneratorInvocationOutputKind",
    "GeneratorOutcomeKind",
    "GeneratorRequest",
    "GeneratorRequestIdentity",
    "GeneratorResult",
    "GeneratorResultRecord",
    "GeneratorTerminalStage",
    "LoadedDependencyIdentity",
    "MaterializationState",
    "NamedApplicabilityReason",
    "NamedConformanceFallback",
    "RecordRefBinding",
    "RecordRefBindingTag",
    "RecordRefPair",
    "ResolvedGeneratorAuthoringBundle",
    "SourceMaterializationState",
    "TerminalReasonCensoringDecision",
    "TerminalReasonFailure",
    "TerminalReasonNotApplicable",
    "TerminalReasonSupportDecision",
]
