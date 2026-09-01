"""Protected, fact-only conformance records for the B-03 fixture runtime.

The module records reached milestones and exact identity comparisons.  It owns
no scientific thresholds, near-duplicate distance, target population, retry
policy, reference truth, score, or qualification decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, final

from carbon.authoring.canonical import (
    CanonicalText,
    encode_value,
    owner_ref_to_canonical,
)
from carbon.authoring.cases import CanonicalChallengeCase
from carbon.authoring.errors import AuthoringError
from carbon.authoring.loading import GraphOriginTag
from carbon.authoring.model import ApplicabilityBinding, ApplicabilityTag
from carbon.authoring.primitives import reconstruct_challenge_key
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    owner_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey

from .accounting import (
    GenerationAccountingSummary,
    IntendedUnitAccounting,
    build_generation_accounting_summary,
)
from .burgers import (
    FixtureDegeneracyFacts,
    FixturePayloadFacts,
    PhysicalPayloadFingerprint,
    ProtectedBurgersFixturePayload,
    ValidatedCaseFacts,
    _new_fixture_degeneracy_facts,
    _new_fixture_payload_facts,
    _new_physical_payload_fingerprint,
    _new_validated_case_facts,
    build_physical_payload_fingerprint,
)
from .errors import GeneratorInputCode, GeneratorValidationError
from .model import (
    GenerationRoleBinding,
    GenerationSourceEvent,
    GeneratorOutcomeKind,
    GeneratorRequest,
    GeneratorRequestIdentity,
    GeneratorResult,
    GeneratorResultRecord,
    GeneratorTerminalStage,
    NamedConformanceFallback,
    RecordRefBinding,
    RecordRefPair,
    SourceMaterializationState,
)
from .refs import (
    BurgersFixtureConfigurationRef,
    ComparisonCorpusDecisionRef,
    DeterministicReplayComparisonRef,
    DuplicateConformanceFactsRef,
    ExternalDistributionFactSetRef,
    FixtureReplayProbeRef,
    GenerationAccountingSummaryRef,
    GeneratorConformanceFactsRef,
    GeneratorEnvironmentRef,
    GeneratorReplayCommitmentRef,
    GeneratorRequestRef,
    GeneratorResultRef,
    IntendedUnitAccountingRef,
    PhysicalPayloadFingerprintRef,
    SupportExclusionDecisionRef,
    reconstruct_generator_ref,
)

_PROBE_RECORD_TOKEN = object()
_PROBE_TOKEN = object()
_REPLAY_COMPARISON_TOKEN = object()


SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID = "support_decision_owner_unavailable"

CONFORMANCE_FALLBACK_SCHEMA = (
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
    SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID,
)

_PAYLOAD_INAPPLICABLE_BY_STAGE = {
    GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY: CONFORMANCE_FALLBACK_SCHEMA[0],
    GeneratorTerminalStage.CONTEXT_ACQUISITION: CONFORMANCE_FALLBACK_SCHEMA[1],
    GeneratorTerminalStage.DERIVATION: CONFORMANCE_FALLBACK_SCHEMA[2],
    GeneratorTerminalStage.MATERIALIZATION: CONFORMANCE_FALLBACK_SCHEMA[3],
}
_SUPPORT_INAPPLICABLE_BY_STAGE = {
    GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY: CONFORMANCE_FALLBACK_SCHEMA[4],
    GeneratorTerminalStage.CONTEXT_ACQUISITION: CONFORMANCE_FALLBACK_SCHEMA[5],
    GeneratorTerminalStage.DERIVATION: CONFORMANCE_FALLBACK_SCHEMA[6],
    GeneratorTerminalStage.MATERIALIZATION: CONFORMANCE_FALLBACK_SCHEMA[7],
}
_VALIDATED_CASE_INAPPLICABLE_BY_STAGE = {
    GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY: CONFORMANCE_FALLBACK_SCHEMA[8],
    GeneratorTerminalStage.CONTEXT_ACQUISITION: CONFORMANCE_FALLBACK_SCHEMA[9],
    GeneratorTerminalStage.DERIVATION: CONFORMANCE_FALLBACK_SCHEMA[10],
    GeneratorTerminalStage.MATERIALIZATION: CONFORMANCE_FALLBACK_SCHEMA[11],
    GeneratorTerminalStage.SUPPORT_AUTHORITY: CONFORMANCE_FALLBACK_SCHEMA[12],
    GeneratorTerminalStage.CASE_CONSTRUCTION: CONFORMANCE_FALLBACK_SCHEMA[13],
    GeneratorTerminalStage.GRAPH_VALIDATION: CONFORMANCE_FALLBACK_SCHEMA[14],
}


def _wrong(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path=path)


def _cross_challenge(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.CROSS_CHALLENGE, path=path)


def _stale(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.STALE_BINDING, path=path)


def _incomplete(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INCOMPLETE_BINDING, path=path)


def _exact(value: object, expected: type, path: str) -> object:
    if type(value) is not expected:
        raise _wrong(path)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    malformed = False
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        malformed = True
    if malformed:
        raise _wrong(path)
    raise AssertionError("unreachable")


def _owner(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    malformed = False
    try:
        copied = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        malformed = True
        copied = None
    if malformed:
        raise _wrong(path)
    scope = copied.scope_binding
    if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return copied


def _top_ref(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    result = _exact(reconstruct_top_level_ref(value), expected, path)
    if result.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return result


def _generator_ref(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    if expected is GeneratorReplayCommitmentRef:
        replay = _exact(value, GeneratorReplayCommitmentRef, path)
        result = GeneratorReplayCommitmentRef(
            replay.challenge_key,
            replay.replay_scheme_id,
            replay.replay_scheme_version,
            replay.reservation_issuer_ref,
            replay.commitment_digest,
        )
    else:
        result = _exact(reconstruct_generator_ref(value), expected, path)
    if result.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return result


def _applicability(
    value: object,
    expected_bound_type: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    binding = _exact(value, ApplicabilityBinding, path)
    if binding.tag is ApplicabilityTag.BOUND:
        _exact(binding.value, expected_bound_type, path)
    else:
        _owner(
            binding.value,
            "applicability_reason",
            challenge_key=challenge_key,
            path=path,
        )
    return binding  # type: ignore[return-value]


def _revalidated_payload_facts_binding(
    value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    """Deep-revalidate protected payload facts hidden behind applicability."""

    binding = _applicability(
        value,
        FixturePayloadFacts,
        challenge_key=challenge_key,
        path=path,
    )
    if not binding.is_bound:
        return binding
    supplied = binding.value
    fingerprint = _exact(
        supplied.physical_payload_fingerprint,
        PhysicalPayloadFingerprint,
        f"{path}/value/physical_payload_fingerprint",
    )
    checked_fingerprint = _new_physical_payload_fingerprint(
        challenge_key=fingerprint.challenge_key,
        case_representation_ref=fingerprint.case_representation_ref,
        fixture_configuration_ref=fingerprint.fixture_configuration_ref,
        protected_payload_digest=fingerprint.protected_payload_digest,
    )
    degeneracy = _exact(
        supplied.degeneracy_facts,
        FixtureDegeneracyFacts,
        f"{path}/value/degeneracy_facts",
    )
    checked_degeneracy = _new_fixture_degeneracy_facts(
        distinct_initial_value_count=degeneracy.distinct_initial_value_count,
        all_initial_values_zero=degeneracy.all_initial_values_zero,
        all_initial_values_identical=degeneracy.all_initial_values_identical,
    )
    checked = _new_fixture_payload_facts(
        protected_payload_ref=supplied.protected_payload_ref,
        physical_payload_fingerprint=checked_fingerprint,
        physical_payload_fingerprint_ref=supplied.physical_payload_fingerprint_ref,
        fixture_configuration_ref=supplied.fixture_configuration_ref,
        spatial_point_count=supplied.spatial_point_count,
        time_point_count=supplied.time_point_count,
        initial_value_count=supplied.initial_value_count,
        degeneracy_facts=checked_degeneracy,
    )
    if checked != supplied:
        raise _stale(path)
    return binding


def _revalidated_case_facts_binding(
    value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    """Deep-revalidate validated-case facts hidden behind applicability."""

    binding = _applicability(
        value,
        ValidatedCaseFacts,
        challenge_key=challenge_key,
        path=path,
    )
    if not binding.is_bound:
        return binding
    supplied = binding.value
    checked = _new_validated_case_facts(
        case_ref=supplied.case_ref,
        representation_ref=supplied.representation_ref,
        physical_payload_ref=supplied.physical_payload_ref,
        primary_population_ref=supplied.primary_population_ref,
        sampling_plan_ref=supplied.sampling_plan_ref,
        graph_origin=supplied.graph_origin,
        origin_evidence_refs=supplied.origin_evidence_refs,
        composition_audit_ref=supplied.composition_audit_ref,
    )
    if checked != supplied:
        raise _stale(path)
    return binding


def _validate_artifact_identity_bindings(
    *,
    identity: GeneratorRequestIdentity,
    source_event: GenerationSourceEvent,
    payload_binding: ApplicabilityBinding,
    case_binding: ApplicabilityBinding,
) -> None:
    """Require every reached artifact fact to echo request-owned bindings."""

    if payload_binding.is_bound:
        payload_facts = payload_binding.value
        fingerprint = payload_facts.physical_payload_fingerprint
        if (
            not source_event.payload_ref_binding.is_bound
            or payload_facts.protected_payload_ref
            != source_event.payload_ref_binding.value
            or payload_facts.fixture_configuration_ref
            != identity.fixture_configuration_ref
            or fingerprint.challenge_key != identity.challenge_key
            or fingerprint.case_representation_ref
            != identity.case_construction.case_representation_ref
            or fingerprint.fixture_configuration_ref
            != identity.fixture_configuration_ref
            or fingerprint.to_ref() != payload_facts.physical_payload_fingerprint_ref
        ):
            raise _stale("/payload_facts_binding")
    if not case_binding.is_bound:
        return
    if not payload_binding.is_bound:
        raise _stale("/constructed_case_facts_binding")
    case_facts = case_binding.value
    construction = identity.case_construction
    loading = identity.fixture_loading
    expected_origin_evidence = (
        loading.origin_evidence_ref,
        *(item.origin_evidence_ref for item in identity.loaded_dependencies),
    )
    if (
        len(expected_origin_evidence) != len(set(expected_origin_evidence))
        or len(case_facts.origin_evidence_refs) != len(expected_origin_evidence)
        or set(case_facts.origin_evidence_refs) != set(expected_origin_evidence)
        or case_facts.case_ref.object_id != construction.object_id
        or case_facts.case_ref.object_version != construction.object_version
        or case_facts.representation_ref != construction.case_representation_ref
        or case_facts.representation_ref
        != payload_binding.value.physical_payload_fingerprint.case_representation_ref
        or case_facts.physical_payload_ref
        != payload_binding.value.protected_payload_ref
        or case_facts.primary_population_ref != identity.primary_population_ref
        or case_facts.sampling_plan_ref != identity.sampling_plan_ref
        or case_facts.graph_origin is not GraphOriginTag.FIXTURE_DERIVED
        or case_facts.composition_audit_ref != loading.composition_audit_ref
    ):
        raise _stale("/constructed_case_facts_binding")


def _pair(value: object, record_type: type, ref_type: type, path: str) -> RecordRefPair:
    result = replace(_exact(value, RecordRefPair, path))
    _exact(result.record, record_type, f"{path}/record")
    _exact(result.ref, ref_type, f"{path}/ref")
    return result  # type: ignore[return-value]


def _record_binding(
    value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> RecordRefBinding:
    binding = _exact(value, RecordRefBinding, path)
    if binding.is_bound:
        pair = _exact(binding.pair, RecordRefPair, f"{path}/pair")
        ref_challenge = getattr(pair.ref, "challenge_key", None)
        if ref_challenge != challenge_key:
            owner_scope = getattr(pair.ref, "scope_binding", None)
            if (
                type(owner_scope) is not ChallengeScope
                or owner_scope.challenge_key != challenge_key
            ):
                raise _cross_challenge(path)
    else:
        _owner(
            binding.reason_ref,
            "applicability_reason",
            challenge_key=challenge_key,
            path=path,
        )
    return binding  # type: ignore[return-value]


def _redacted(type_name: str) -> str:
    return f"{type_name}(<protected>)"


def _reject_pickle(type_name: str) -> None:
    raise TypeError(f"{type_name} does not support generic serialization")


_OUTCOME_STAGE_MATRIX = {
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
            GeneratorTerminalStage.GRAPH_VALIDATION,
            GeneratorTerminalStage.CENSORING_AUTHORITY,
            GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
        }
    ),
}


@final
@dataclass(frozen=True, slots=True, repr=False)
class ReplayIdentityFacts:
    """Current-invocation identities only; this makes no replay comparison."""

    request_identity: GeneratorRequestIdentity
    request_ref: GeneratorRequestRef
    source_event: GenerationSourceEvent
    source_event_ref: object
    replay_ref: GeneratorReplayCommitmentRef
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    materialization_state: SourceMaterializationState
    payload_facts_binding: ApplicabilityBinding[FixturePayloadFacts]
    constructed_case_facts_binding: ApplicabilityBinding[ValidatedCaseFacts]

    def __post_init__(self) -> None:
        if type(self) is not ReplayIdentityFacts:
            raise _wrong("/replay_identity_facts")
        identity = _exact(
            self.request_identity,
            GeneratorRequestIdentity,
            "/request_identity",
        )
        key = identity.challenge_key
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        if identity.to_ref() != request_ref:
            raise _stale("/request_ref")
        event = _exact(self.source_event, GenerationSourceEvent, "/source_event")
        event_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        if event.challenge_key != key or event.to_ref() != event_ref:
            raise _stale("/source_event_ref")
        replay_ref = _generator_ref(
            self.replay_ref,
            GeneratorReplayCommitmentRef,
            challenge_key=key,
            path="/replay_ref",
        )
        generator_ref = _owner(
            self.generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        environment_ref = _generator_ref(
            self.environment_ref,
            GeneratorEnvironmentRef,
            challenge_key=key,
            path="/environment_ref",
        )
        configuration_ref = _generator_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            challenge_key=key,
            path="/fixture_configuration_ref",
        )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        state = _exact(
            self.materialization_state,
            SourceMaterializationState,
            "/materialization_state",
        )
        expected = (
            (event.request_ref, request_ref),
            (event.replay_ref, replay_ref),
            (event.generator_ref, generator_ref),
            (event.environment_ref, environment_ref),
            (event.fixture_configuration_ref, configuration_ref),
            (event.role_binding, role),
            (event.materialization_state, state),
            (identity.generator_ref, generator_ref),
            (identity.environment_ref, environment_ref),
            (identity.fixture_configuration_ref, configuration_ref),
            (identity.role_binding, role),
            (identity.replay_ref, replay_ref),
        )
        if any(actual != wanted for actual, wanted in expected):
            raise _stale("/replay_identity_facts")
        payload_binding = _revalidated_payload_facts_binding(
            self.payload_facts_binding,
            challenge_key=key,
            path="/payload_facts_binding",
        )
        case_binding = _revalidated_case_facts_binding(
            self.constructed_case_facts_binding,
            challenge_key=key,
            path="/constructed_case_facts_binding",
        )
        if payload_binding.is_bound != (
            state is SourceMaterializationState.PAYLOAD_AVAILABLE
        ):
            raise _invalid("/payload_facts_binding")
        _validate_artifact_identity_bindings(
            identity=identity,
            source_event=event,
            payload_binding=payload_binding,
            case_binding=case_binding,
        )
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_ref", event_ref)
        object.__setattr__(self, "generator_ref", generator_ref)
        object.__setattr__(self, "environment_ref", environment_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class GeneratorConformanceFacts:
    """Exact reached-milestone facts for one admitted terminal invocation."""

    challenge_key: ChallengeKey
    request_identity: GeneratorRequestIdentity
    request_ref: GeneratorRequestRef
    source_event: GenerationSourceEvent
    source_event_ref: object
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    role_binding: GenerationRoleBinding
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    payload_facts_binding: ApplicabilityBinding[FixturePayloadFacts]
    support_decision_binding: RecordRefBinding
    validated_case_facts_binding: ApplicabilityBinding[ValidatedCaseFacts]
    replay_identity_facts: ReplayIdentityFacts

    def __post_init__(self) -> None:
        if type(self) is not GeneratorConformanceFacts:
            raise _wrong("/conformance_facts")
        key = _challenge(self.challenge_key)
        identity = _exact(
            self.request_identity,
            GeneratorRequestIdentity,
            "/request_identity",
        )
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        event = _exact(self.source_event, GenerationSourceEvent, "/source_event")
        event_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        if (
            identity.challenge_key != key
            or identity.to_ref() != request_ref
            or event.challenge_key != key
            or event.to_ref() != event_ref
            or event.request_ref != request_ref
        ):
            raise _stale("/request_ref")
        generator_ref = _owner(
            self.generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        environment_ref = _generator_ref(
            self.environment_ref,
            GeneratorEnvironmentRef,
            challenge_key=key,
            path="/environment_ref",
        )
        configuration_ref = _generator_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            challenge_key=key,
            path="/fixture_configuration_ref",
        )
        primary_ref = _top_ref(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/primary_population_ref",
        )
        selection_ref = _top_ref(
            self.selection_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/selection_population_ref",
        )
        plan_ref = _top_ref(
            self.sampling_plan_ref,
            SamplingPlanRef,
            challenge_key=key,
            path="/sampling_plan_ref",
        )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        outcome = _exact(self.outcome_kind, GeneratorOutcomeKind, "/outcome_kind")
        stage = _exact(self.terminal_stage, GeneratorTerminalStage, "/terminal_stage")
        if stage not in _OUTCOME_STAGE_MATRIX[outcome]:
            raise _invalid("/terminal_stage")
        fallbacks = _conformance_fallbacks(identity)
        conformance_rows = _conformance_rows(fallbacks)
        expected = (
            (identity.generator_ref, generator_ref),
            (identity.environment_ref, environment_ref),
            (identity.fixture_configuration_ref, configuration_ref),
            (identity.primary_population_ref, primary_ref),
            (identity.selection_population_ref, selection_ref),
            (identity.sampling_plan_ref, plan_ref),
            (identity.role_binding, role),
            (event.generator_ref, generator_ref),
            (event.environment_ref, environment_ref),
            (event.fixture_configuration_ref, configuration_ref),
            (event.primary_population_ref, primary_ref),
            (event.selection_population_ref, selection_ref),
            (event.sampling_plan_ref, plan_ref),
            (event.role_binding, role),
        )
        if any(actual != wanted for actual, wanted in expected):
            raise _stale("/conformance_facts")
        payload_binding = _revalidated_payload_facts_binding(
            self.payload_facts_binding,
            challenge_key=key,
            path="/payload_facts_binding",
        )
        support_binding = _record_binding(
            self.support_decision_binding,
            challenge_key=key,
            path="/support_decision_binding",
        )
        if support_binding.is_bound:
            from .authorities import (
                SupportExclusionDecision,
                SupportExclusionDecisionKind,
            )

            support_pair = _pair(
                support_binding.pair,
                SupportExclusionDecision,
                SupportExclusionDecisionRef,
                "/support_decision_binding/pair",
            )
            support_decision = support_pair.record
            support_request = support_decision.request
            if (
                support_request.generator_request_ref != request_ref
                or support_request.source_event != event
                or support_request.source_event_ref != event_ref
                or support_request.fixture_configuration_ref != configuration_ref
                or support_request.primary_population_ref != primary_ref
                or support_request.selection_population_ref != selection_ref
                or support_request.sampling_plan_ref != plan_ref
                or support_request.role_binding != role
            ):
                raise _stale("/support_decision_binding")
            if (
                support_decision.decision_kind
                is SupportExclusionDecisionKind.OWNER_UNAVAILABLE
                and support_decision.infrastructure_failure_ref
                != fallbacks[SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID]
            ):
                raise _stale("/support_decision_binding")
        validated_binding = _revalidated_case_facts_binding(
            self.validated_case_facts_binding,
            challenge_key=key,
            path="/validated_case_facts_binding",
        )
        replay = _exact(
            self.replay_identity_facts,
            ReplayIdentityFacts,
            "/replay_identity_facts",
        )
        if (
            replay.request_identity != identity
            or replay.request_ref != request_ref
            or replay.source_event != event
            or replay.source_event_ref != event_ref
            or replay.generator_ref != generator_ref
            or replay.environment_ref != environment_ref
            or replay.fixture_configuration_ref != configuration_ref
            or replay.role_binding != role
            or replay.payload_facts_binding != payload_binding
            or replay.constructed_case_facts_binding != validated_binding
        ):
            raise _stale("/replay_identity_facts")
        if payload_binding.is_bound != (
            event.materialization_state is SourceMaterializationState.PAYLOAD_AVAILABLE
        ):
            raise _invalid("/payload_facts_binding")
        if support_binding.is_bound and (
            support_request.fixture_payload_facts != payload_binding.value
            or support_request.protected_payload_ref
            != payload_binding.value.protected_payload_ref
        ):
            raise _stale("/support_decision_binding")
        if validated_binding.is_bound and not support_binding.is_bound:
            raise _invalid("/validated_case_facts_binding")
        if support_binding.is_bound and not payload_binding.is_bound:
            raise _invalid("/support_decision_binding")
        _validate_artifact_identity_bindings(
            identity=identity,
            source_event=event,
            payload_binding=payload_binding,
            case_binding=validated_binding,
        )
        observed_row = _observed_conformance_row(
            payload_binding,
            support_binding,
            validated_binding,
        )
        if stage is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY:
            if observed_row not in frozenset(conformance_rows.values()):
                raise _stale("/terminal_stage")
        elif observed_row != conformance_rows[stage]:
            raise _stale("/terminal_stage")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_ref", event_ref)
        object.__setattr__(self, "generator_ref", generator_ref)
        object.__setattr__(self, "environment_ref", environment_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(self, "primary_population_ref", primary_ref)
        object.__setattr__(self, "selection_population_ref", selection_ref)
        object.__setattr__(self, "sampling_plan_ref", plan_ref)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GeneratorConformanceFactsRef:
        from .canonical import _record_ref

        return _record_ref(self, GeneratorConformanceFactsRef)  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def _conformance_fallbacks(
    identity: GeneratorRequestIdentity,
) -> dict[str, object]:
    checked_identity = _exact(
        identity,
        GeneratorRequestIdentity,
        "/request_identity",
    )
    values = checked_identity.conformance_fallbacks
    if (
        type(values) is not tuple
        or len(values) != len(CONFORMANCE_FALLBACK_SCHEMA)
        or any(type(item) is not NamedConformanceFallback for item in values)
        or tuple(item.fallback_id for item in values) != CONFORMANCE_FALLBACK_SCHEMA
    ):
        raise _invalid("/request_identity/conformance_fallbacks")
    result: dict[str, object] = {}
    for index, item in enumerate(values):
        expected_kind = (
            "infrastructure_failure"
            if item.fallback_id == SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID
            else "applicability_reason"
        )
        result[item.fallback_id] = _owner(
            item.fallback_ref,
            expected_kind,
            challenge_key=checked_identity.challenge_key,
            path=f"/request_identity/conformance_fallbacks/{index}/fallback_ref",
        )
    if len(set(result.values())) != len(result):
        raise _invalid("/request_identity/conformance_fallbacks")
    return result


def _conformance_rows(
    fallbacks: dict[str, object],
) -> dict[GeneratorTerminalStage, tuple[object | None, object | None, object | None]]:
    bound = None
    return {
        GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY: (
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[0]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[4]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[8]],
        ),
        GeneratorTerminalStage.CONTEXT_ACQUISITION: (
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[1]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[5]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[9]],
        ),
        GeneratorTerminalStage.DERIVATION: (
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[2]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[6]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[10]],
        ),
        GeneratorTerminalStage.MATERIALIZATION: (
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[3]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[7]],
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[11]],
        ),
        GeneratorTerminalStage.SUPPORT_AUTHORITY: (
            bound,
            bound,
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[12]],
        ),
        GeneratorTerminalStage.CASE_CONSTRUCTION: (
            bound,
            bound,
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[13]],
        ),
        GeneratorTerminalStage.GRAPH_VALIDATION: (
            bound,
            bound,
            fallbacks[CONFORMANCE_FALLBACK_SCHEMA[14]],
        ),
        GeneratorTerminalStage.CENSORING_AUTHORITY: (bound, bound, bound),
        GeneratorTerminalStage.CENSORING_COMPLETION: (bound, bound, bound),
    }


def _observed_conformance_row(
    payload_binding: ApplicabilityBinding,
    support_binding: RecordRefBinding,
    validated_binding: ApplicabilityBinding,
) -> tuple[object | None, object | None, object | None]:
    return (
        None if payload_binding.is_bound else payload_binding.value,
        None if support_binding.is_bound else support_binding.reason_ref,
        None if validated_binding.is_bound else validated_binding.value,
    )


def build_generator_conformance_facts(
    *,
    request: GeneratorRequest,
    source_event: GenerationSourceEvent,
    source_event_ref: object,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
    applicability_stage: GeneratorTerminalStage,
    payload_facts: FixturePayloadFacts | None,
    support_decision: object | None,
    support_decision_ref: object | None,
    validated_case_facts: ValidatedCaseFacts | None,
) -> tuple[GeneratorConformanceFacts, GeneratorConformanceFactsRef]:
    """Derive every applicability binding from reached milestones and fallbacks."""

    checked_request = _exact(request, GeneratorRequest, "/request")
    identity = checked_request.identity()
    request_ref = identity.to_ref()
    event = _exact(source_event, GenerationSourceEvent, "/source_event")
    event_ref = _owner(
        source_event_ref,
        "generation_event",
        challenge_key=identity.challenge_key,
        path="/source_event_ref",
    )
    if (
        event.to_ref() != event_ref
        or event.request_ref != request_ref
        or event.challenge_key != identity.challenge_key
    ):
        raise _stale("/source_event")
    outcome = _exact(outcome_kind, GeneratorOutcomeKind, "/outcome_kind")
    terminal = _exact(
        terminal_stage,
        GeneratorTerminalStage,
        "/terminal_stage",
    )
    reached = _exact(
        applicability_stage,
        GeneratorTerminalStage,
        "/applicability_stage",
    )
    if terminal is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY:
        if reached is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY:
            raise _invalid("/applicability_stage")
    elif reached is not terminal:
        raise _stale("/applicability_stage")
    fallbacks = _conformance_fallbacks(identity)

    payload_reason_id = _PAYLOAD_INAPPLICABLE_BY_STAGE.get(reached)
    if payload_reason_id is None:
        payload = _exact(payload_facts, FixturePayloadFacts, "/payload_facts")
        if (
            event.materialization_state
            is not SourceMaterializationState.PAYLOAD_AVAILABLE
        ):
            raise _stale("/payload_facts")
        payload_binding = ApplicabilityBinding.bound(payload)
    else:
        if payload_facts is not None:
            raise _invalid("/payload_facts")
        if event.materialization_state is SourceMaterializationState.PAYLOAD_AVAILABLE:
            raise _stale("/payload_facts")
        payload_binding = ApplicabilityBinding.not_applicable(
            fallbacks[payload_reason_id]
        )

    support_reason_id = _SUPPORT_INAPPLICABLE_BY_STAGE.get(reached)
    if support_reason_id is None:
        from .authorities import SupportExclusionDecision

        support = _exact(
            support_decision,
            SupportExclusionDecision,
            "/support_decision",
        )
        support_ref = _generator_ref(
            support_decision_ref,
            SupportExclusionDecisionRef,
            challenge_key=identity.challenge_key,
            path="/support_decision_ref",
        )
        if (
            support.to_ref() != support_ref
            or support.request.generator_request_ref != request_ref
        ):
            raise _stale("/support_decision")
        support_binding = RecordRefBinding.bound(support, support_ref)
    else:
        if support_decision is not None or support_decision_ref is not None:
            raise _invalid("/support_decision")
        support_binding = RecordRefBinding.not_applicable(fallbacks[support_reason_id])

    validated_reason_id = _VALIDATED_CASE_INAPPLICABLE_BY_STAGE.get(reached)
    if validated_reason_id is None:
        validated = _exact(
            validated_case_facts,
            ValidatedCaseFacts,
            "/validated_case_facts",
        )
        validated_binding = ApplicabilityBinding.bound(validated)
    else:
        if validated_case_facts is not None:
            raise _invalid("/validated_case_facts")
        validated_binding = ApplicabilityBinding.not_applicable(
            fallbacks[validated_reason_id]
        )

    if support_binding.is_bound and not payload_binding.is_bound:
        raise _invalid("/support_decision")
    if validated_binding.is_bound and not support_binding.is_bound:
        raise _invalid("/validated_case_facts")
    replay = ReplayIdentityFacts(
        request_identity=identity,
        request_ref=request_ref,
        source_event=event,
        source_event_ref=event_ref,
        replay_ref=identity.replay_ref,
        generator_ref=identity.generator_ref,
        environment_ref=identity.environment_ref,
        fixture_configuration_ref=identity.fixture_configuration_ref,
        role_binding=identity.role_binding,
        materialization_state=event.materialization_state,
        payload_facts_binding=payload_binding,
        constructed_case_facts_binding=validated_binding,
    )
    facts = GeneratorConformanceFacts(
        challenge_key=identity.challenge_key,
        request_identity=identity,
        request_ref=request_ref,
        source_event=event,
        source_event_ref=event_ref,
        generator_ref=identity.generator_ref,
        environment_ref=identity.environment_ref,
        fixture_configuration_ref=identity.fixture_configuration_ref,
        primary_population_ref=identity.primary_population_ref,
        selection_population_ref=identity.selection_population_ref,
        sampling_plan_ref=identity.sampling_plan_ref,
        role_binding=identity.role_binding,
        outcome_kind=outcome,
        terminal_stage=terminal,
        payload_facts_binding=payload_binding,
        support_decision_binding=support_binding,
        validated_case_facts_binding=validated_binding,
        replay_identity_facts=replay,
    )
    return facts, facts.to_ref()


def _case_pair_from_result(
    record: GeneratorResultRecord,
    *,
    path: str = "/baseline_result",
) -> RecordRefPair:
    binding = record.case_binding
    if not binding.is_bound:
        raise _incomplete(f"{path}/case_binding")
    return _pair(
        binding.pair,
        CanonicalChallengeCase,
        CanonicalChallengeCaseRef,
        f"{path}/case_binding/pair",
    )


def _payload_facts_from_result(
    record: GeneratorResultRecord,
    *,
    path: str = "/baseline_result",
) -> FixturePayloadFacts:
    facts = _exact(
        record.conformance_facts,
        GeneratorConformanceFacts,
        f"{path}/conformance_facts",
    )
    if facts.to_ref() != record.conformance_facts_ref:
        raise _stale(f"{path}/conformance_facts_ref")
    binding = facts.payload_facts_binding
    if not binding.is_bound:
        raise _incomplete(f"{path}/payload_facts_binding")
    return _exact(
        binding.value,
        FixturePayloadFacts,
        f"{path}/payload_facts_binding",
    )  # type: ignore[return-value]


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class FixtureReplayProbeRecord:
    """Canonical audit-only reconstruction record; never an invocation result."""

    baseline_result: GeneratorResultRecord
    baseline_result_ref: GeneratorResultRef
    baseline_request_identity: GeneratorRequestIdentity
    baseline_request_ref: GeneratorRequestRef
    replay_ref: GeneratorReplayCommitmentRef
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    role_binding: GenerationRoleBinding
    observed_physical_payload_fingerprint: PhysicalPayloadFingerprint
    observed_physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef
    reconstructed_protected_payload_ref: object
    reconstructed_source_event_ref: object
    reconstructed_case_ref: CanonicalChallengeCaseRef

    def __init__(
        self,
        *,
        baseline_result: object,
        baseline_result_ref: object,
        baseline_request_identity: object,
        baseline_request_ref: object,
        replay_ref: object,
        generator_ref: object,
        environment_ref: object,
        fixture_configuration_ref: object,
        role_binding: object,
        observed_physical_payload_fingerprint: object,
        observed_physical_payload_fingerprint_ref: object,
        reconstructed_protected_payload_ref: object,
        reconstructed_source_event_ref: object,
        reconstructed_case_ref: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not FixtureReplayProbeRecord
            or _token is not _PROBE_RECORD_TOKEN
        ):
            raise _wrong("/fixture_replay_probe")
        result = _exact(baseline_result, GeneratorResultRecord, "/baseline_result")
        key = result.challenge_key
        result_ref = _generator_ref(
            baseline_result_ref,
            GeneratorResultRef,
            challenge_key=key,
            path="/baseline_result_ref",
        )
        if result.to_ref() != result_ref:
            raise _stale("/baseline_result_ref")
        request_identity = _exact(
            baseline_request_identity,
            GeneratorRequestIdentity,
            "/baseline_request_identity",
        )
        request_ref = _generator_ref(
            baseline_request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/baseline_request_ref",
        )
        if (
            request_identity.to_ref() != request_ref
            or result.request_ref != request_ref
        ):
            raise _stale("/baseline_request_ref")
        replay = _generator_ref(
            replay_ref,
            GeneratorReplayCommitmentRef,
            challenge_key=key,
            path="/replay_ref",
        )
        generator = _owner(
            generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        environment = _generator_ref(
            environment_ref,
            GeneratorEnvironmentRef,
            challenge_key=key,
            path="/environment_ref",
        )
        configuration = _generator_ref(
            fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            challenge_key=key,
            path="/fixture_configuration_ref",
        )
        role = _exact(role_binding, GenerationRoleBinding, "/role_binding")
        expected = (
            (result.source_event.replay_ref, replay),
            (result.generator_ref, generator),
            (result.environment_ref, environment),
            (result.fixture_configuration_ref, configuration),
            (result.role_binding, role),
            (request_identity.replay_ref, replay),
            (request_identity.generator_ref, generator),
            (request_identity.environment_ref, environment),
            (request_identity.fixture_configuration_ref, configuration),
            (request_identity.role_binding, role),
        )
        if any(actual != wanted for actual, wanted in expected):
            raise _stale("/fixture_replay_probe")
        case_pair = _case_pair_from_result(result)
        fingerprint = _exact(
            observed_physical_payload_fingerprint,
            PhysicalPayloadFingerprint,
            "/observed_physical_payload_fingerprint",
        )
        fingerprint_ref = _generator_ref(
            observed_physical_payload_fingerprint_ref,
            PhysicalPayloadFingerprintRef,
            challenge_key=key,
            path="/observed_physical_payload_fingerprint_ref",
        )
        if (
            fingerprint.to_ref() != fingerprint_ref
            or fingerprint.challenge_key != key
            or fingerprint.case_representation_ref
            != case_pair.record.case_representation_ref
            or fingerprint.fixture_configuration_ref != configuration
        ):
            raise _stale("/observed_physical_payload_fingerprint")
        payload_ref = _owner(
            reconstructed_protected_payload_ref,
            "protected_case_payload",
            challenge_key=key,
            path="/reconstructed_protected_payload_ref",
        )
        source_event_ref = _owner(
            reconstructed_source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/reconstructed_source_event_ref",
        )
        case_ref = _top_ref(
            reconstructed_case_ref,
            CanonicalChallengeCaseRef,
            challenge_key=key,
            path="/reconstructed_case_ref",
        )
        object.__setattr__(self, "baseline_result", result)
        object.__setattr__(self, "baseline_result_ref", result_ref)
        object.__setattr__(self, "baseline_request_identity", request_identity)
        object.__setattr__(self, "baseline_request_ref", request_ref)
        object.__setattr__(self, "replay_ref", replay)
        object.__setattr__(self, "generator_ref", generator)
        object.__setattr__(self, "environment_ref", environment)
        object.__setattr__(self, "fixture_configuration_ref", configuration)
        object.__setattr__(self, "role_binding", role)
        object.__setattr__(self, "observed_physical_payload_fingerprint", fingerprint)
        object.__setattr__(
            self, "observed_physical_payload_fingerprint_ref", fingerprint_ref
        )
        object.__setattr__(self, "reconstructed_protected_payload_ref", payload_ref)
        object.__setattr__(self, "reconstructed_source_event_ref", source_event_ref)
        object.__setattr__(self, "reconstructed_case_ref", case_ref)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> FixtureReplayProbeRef:
        from .canonical import _record_ref

        return _record_ref(
            self,
            FixtureReplayProbeRef,
            challenge_key=self.baseline_result.challenge_key,
        )  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def _new_fixture_replay_probe_record(**kwargs: object) -> FixtureReplayProbeRecord:
    return FixtureReplayProbeRecord(**kwargs, _token=_PROBE_RECORD_TOKEN)


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class FixtureReplayProbe:
    """Noncanonical wrapper retaining reconstructed protected objects."""

    record: FixtureReplayProbeRecord
    ref: FixtureReplayProbeRef
    protected_payload: ProtectedBurgersFixturePayload
    source_event: GenerationSourceEvent
    case: CanonicalChallengeCase

    def __init__(
        self,
        *,
        record: object,
        ref: object,
        protected_payload: object,
        source_event: object,
        case: object,
        _token: object,
    ) -> None:
        if type(self) is not FixtureReplayProbe or _token is not _PROBE_TOKEN:
            raise _wrong("/fixture_replay_probe")
        probe_record = _exact(record, FixtureReplayProbeRecord, "/record")
        key = probe_record.baseline_result.challenge_key
        probe_ref = _generator_ref(
            ref,
            FixtureReplayProbeRef,
            challenge_key=key,
            path="/ref",
        )
        if probe_record.to_ref() != probe_ref:
            raise _stale("/ref")
        payload = _exact(
            protected_payload,
            ProtectedBurgersFixturePayload,
            "/protected_payload",
        )
        event = _exact(source_event, GenerationSourceEvent, "/source_event")
        reconstructed_case = _exact(case, CanonicalChallengeCase, "/case")
        from .canonical import canonical_content_digest

        if (
            payload.fixture_configuration_ref != probe_record.fixture_configuration_ref
            or probe_record.reconstructed_protected_payload_ref.content_digest
            != canonical_content_digest(payload)
            or event.to_ref() != probe_record.reconstructed_source_event_ref
            or reconstructed_case.to_ref() != probe_record.reconstructed_case_ref
            or not event.payload_ref_binding.is_bound
            or event.payload_ref_binding.value
            != probe_record.reconstructed_protected_payload_ref
        ):
            raise _stale("/fixture_replay_probe")
        recomputed_fingerprint = build_physical_payload_fingerprint(
            challenge_key=key,
            case_representation_ref=reconstructed_case.case_representation_ref,
            fixture_configuration_ref=payload.fixture_configuration_ref,
            protected_payload=payload,
        )
        if (
            recomputed_fingerprint != probe_record.observed_physical_payload_fingerprint
            or recomputed_fingerprint.to_ref()
            != probe_record.observed_physical_payload_fingerprint_ref
        ):
            raise _stale("/observed_physical_payload_fingerprint")
        object.__setattr__(self, "record", probe_record)
        object.__setattr__(self, "ref", probe_ref)
        object.__setattr__(self, "protected_payload", payload)
        object.__setattr__(self, "source_event", event)
        object.__setattr__(self, "case", reconstructed_case)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def _new_fixture_replay_probe(
    *,
    record: object,
    ref: object,
    protected_payload: object,
    source_event: object,
    case: object,
) -> FixtureReplayProbe:
    return FixtureReplayProbe(
        record=record,
        ref=ref,
        protected_payload=protected_payload,
        source_event=source_event,
        case=case,
        _token=_PROBE_TOKEN,
    )


def _prepare_fixture_replay_probe(
    *,
    baseline_result: object,
    baseline_result_ref: object,
    baseline_request: object,
) -> tuple[object, ...]:
    """Deeply reconstruct a complete case-bearing baseline without mutation."""

    from .burgers import build_generated_fixture_artifact
    from .service import (
        _validate_generator_request_content,
        build_generated_case,
        build_generation_source_event,
    )

    request_value = _exact(baseline_request, GeneratorRequest, "/baseline_request")
    result_value = _exact(baseline_result, GeneratorResult, "/baseline_result")
    reconstruction_failed = False
    validation_failure = None
    try:
        request = replace(request_value)
        _, identity, request_ref = _validate_generator_request_content(request)
        result = replace(result_value)
    except GeneratorValidationError as exc:
        validation_failure = (exc.code, exc.path)
        request = None
        identity = None
        request_ref = None
        result = None
    except Exception:  # noqa: BLE001 - convert malformed protected graphs.
        reconstruction_failed = True
        request = None
        identity = None
        request_ref = None
        result = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if reconstruction_failed:
        raise _stale("/baseline_result")
    assert type(request) is GeneratorRequest
    assert type(identity) is GeneratorRequestIdentity
    assert type(request_ref) is GeneratorRequestRef
    assert type(result) is GeneratorResult
    result_ref = _generator_ref(
        baseline_result_ref,
        GeneratorResultRef,
        challenge_key=result.record.challenge_key,
        path="/baseline_result_ref",
    )
    if (
        result.ref != result_ref
        or result.record.to_ref() != result_ref
        or result.record.request_ref != request_ref
        or result.record.challenge_key != identity.challenge_key
        or result.record.generator_ref != identity.generator_ref
        or result.record.environment_ref != identity.environment_ref
        or result.record.fixture_configuration_ref != identity.fixture_configuration_ref
        or result.record.role_binding != identity.role_binding
        or result.record.physical_system_ref != identity.physical_system_ref
        or result.record.candidate_output_ref != identity.candidate_output_ref
        or result.record.primary_population_ref != identity.primary_population_ref
        or result.record.selection_population_ref != identity.selection_population_ref
        or result.record.sampling_plan_ref != identity.sampling_plan_ref
        or result.record.fixture_registration_ref
        != request.generator.fixture_registration_ref
        or result.record.source_provenance_refs
        != request.generator.source_provenance_refs
    ):
        raise _stale("/baseline_result")
    case_pair = _case_pair_from_result(result.record)
    reconstructed_baseline_case = replace(case_pair.record)
    if (
        result.artifact is None
        or reconstructed_baseline_case != case_pair.record
        or result.artifact.case != reconstructed_baseline_case
        or result.artifact.case_ref != case_pair.ref
    ):
        raise _incomplete("/baseline_result/artifact")
    reconstructed_artifact = build_generated_fixture_artifact(
        case=reconstructed_baseline_case,
        case_ref=case_pair.ref,
        loaded_case=result.artifact.loaded_case,
        loaded_dependencies=result.artifact.loaded_dependencies,
        graph_origin=result.artifact.graph_origin,
    )
    if reconstructed_artifact != result.artifact:
        raise _stale("/baseline_result/artifact")
    baseline_payload_facts = _payload_facts_from_result(result.record)
    conformance_facts = result.record.conformance_facts
    if (
        conformance_facts.request_identity != identity
        or conformance_facts.request_ref != request_ref
        or conformance_facts.source_event != result.record.source_event
        or conformance_facts.source_event_ref != result.record.source_event_ref
    ):
        raise _stale("/baseline_result/conformance_facts")
    baseline_event = replace(result.record.source_event)
    if (
        baseline_event != result.record.source_event
        or not baseline_event.payload_ref_binding.is_bound
        or baseline_event.payload_ref_binding.value
        != baseline_payload_facts.protected_payload_ref
    ):
        raise _stale("/baseline_result/source_event")
    expected_event = build_generation_source_event(
        request,
        payload_ref=baseline_payload_facts.protected_payload_ref,
        materialization_state=SourceMaterializationState.PAYLOAD_AVAILABLE,
    )
    expected_case = build_generated_case(
        request,
        source_event=expected_event,
        payload_ref=baseline_payload_facts.protected_payload_ref,
    )
    if (
        expected_event != baseline_event
        or expected_event.to_ref() != result.record.source_event_ref
        or expected_case != case_pair.record
        or expected_case.to_ref() != case_pair.ref
        or expected_case.physical_payload_ref
        != baseline_payload_facts.protected_payload_ref
        or baseline_payload_facts.fixture_configuration_ref
        != identity.fixture_configuration_ref
        or baseline_payload_facts.physical_payload_fingerprint.challenge_key
        != identity.challenge_key
        or baseline_payload_facts.physical_payload_fingerprint.case_representation_ref
        != request.case_construction.case_representation_ref
        or baseline_payload_facts.physical_payload_fingerprint.fixture_configuration_ref
        != identity.fixture_configuration_ref
        or baseline_payload_facts.physical_payload_fingerprint.to_ref()
        != baseline_payload_facts.physical_payload_fingerprint_ref
        or result.record.source_event.request_ref != request_ref
    ):
        raise _stale("/baseline_result")
    return (
        request,
        identity,
        request_ref,
        result,
        result_ref,
        baseline_payload_facts,
    )


def _build_fixture_replay_probe_from_payload(
    prepared: tuple[object, ...],
    protected_payload: object,
) -> FixtureReplayProbe:
    """Build the protected replay record after its one-use authority claim."""

    from .canonical import canonical_content_digest
    from .service import build_generated_case, build_generation_source_event

    if type(prepared) is not tuple or len(prepared) != 6:
        raise _wrong("/baseline_result")
    request, identity, request_ref, result, result_ref, baseline_payload_facts = (
        prepared
    )
    request = _exact(request, GeneratorRequest, "/baseline_request")
    identity = _exact(
        identity,
        GeneratorRequestIdentity,
        "/baseline_request_identity",
    )
    request_ref = _generator_ref(
        request_ref,
        GeneratorRequestRef,
        challenge_key=identity.challenge_key,
        path="/baseline_request_ref",
    )
    result = _exact(result, GeneratorResult, "/baseline_result")
    result_ref = _generator_ref(
        result_ref,
        GeneratorResultRef,
        challenge_key=identity.challenge_key,
        path="/baseline_result_ref",
    )
    baseline_payload_facts = _exact(
        baseline_payload_facts,
        FixturePayloadFacts,
        "/baseline_result/conformance_facts/payload_facts_binding",
    )
    payload = _exact(
        protected_payload,
        ProtectedBurgersFixturePayload,
        "/protected_payload",
    )
    payload_ref = owner_ref(
        "protected_case_payload",
        scope_binding=ChallengeScope(identity.challenge_key),
        object_id=identity.attempt_ref.object_id,
        object_version=identity.attempt_ref.object_version,
        content_digest=canonical_content_digest(payload),
    )
    fingerprint = build_physical_payload_fingerprint(
        challenge_key=identity.challenge_key,
        case_representation_ref=request.case_construction.case_representation_ref,
        fixture_configuration_ref=identity.fixture_configuration_ref,
        protected_payload=payload,
    )
    source_event = build_generation_source_event(
        request,
        payload_ref=payload_ref,
        materialization_state=SourceMaterializationState.PAYLOAD_AVAILABLE,
    )
    reconstructed_case = build_generated_case(
        request,
        source_event=source_event,
        payload_ref=payload_ref,
    )
    record = _new_fixture_replay_probe_record(
        baseline_result=result.record,
        baseline_result_ref=result_ref,
        baseline_request_identity=identity,
        baseline_request_ref=request_ref,
        replay_ref=identity.replay_ref,
        generator_ref=identity.generator_ref,
        environment_ref=identity.environment_ref,
        fixture_configuration_ref=identity.fixture_configuration_ref,
        role_binding=identity.role_binding,
        observed_physical_payload_fingerprint=fingerprint,
        observed_physical_payload_fingerprint_ref=fingerprint.to_ref(),
        reconstructed_protected_payload_ref=payload_ref,
        reconstructed_source_event_ref=source_event.to_ref(),
        reconstructed_case_ref=reconstructed_case.to_ref(),
    )
    return _new_fixture_replay_probe(
        record=record,
        ref=record.to_ref(),
        protected_payload=payload,
        source_event=source_event,
        case=reconstructed_case,
    )


def build_fixture_replay_probe(
    *,
    baseline_result: GeneratorResult,
    baseline_result_ref: GeneratorResultRef,
    baseline_request: GeneratorRequest,
    replay_authority: object,
) -> FixtureReplayProbe:
    """Delegate one complete replay operation to the exact nominal authority."""

    from .authorities import FixtureReplayProbeAuthority

    authority = _exact(
        replay_authority,
        FixtureReplayProbeAuthority,
        "/replay_authority",
    )
    probe = authority.probe(
        baseline_result=baseline_result,
        baseline_result_ref=baseline_result_ref,
        baseline_request=baseline_request,
    )
    return _exact(probe, FixtureReplayProbe, "/fixture_replay_probe")  # type: ignore[return-value]


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class DeterministicReplayComparison:
    """Derived exact equality facts for one baseline and one audit probe."""

    baseline_result_ref: GeneratorResultRef
    baseline_source_event_ref: object
    baseline_physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef
    baseline_case_ref: CanonicalChallengeCaseRef
    probe: FixtureReplayProbeRecord
    probe_ref: FixtureReplayProbeRef
    observed_physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef
    reconstructed_protected_payload_ref: object
    reconstructed_source_event_ref: object
    reconstructed_case_ref: CanonicalChallengeCaseRef
    physical_payload_fingerprint_equal: bool
    source_event_bytes_and_ref_equal: bool
    case_bytes_and_ref_equal: bool

    def __init__(
        self,
        *,
        baseline_result_ref: object,
        baseline_source_event_ref: object,
        baseline_physical_payload_fingerprint_ref: object,
        baseline_case_ref: object,
        probe: object,
        probe_ref: object,
        observed_physical_payload_fingerprint_ref: object,
        reconstructed_protected_payload_ref: object,
        reconstructed_source_event_ref: object,
        reconstructed_case_ref: object,
        physical_payload_fingerprint_equal: object,
        source_event_bytes_and_ref_equal: object,
        case_bytes_and_ref_equal: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not DeterministicReplayComparison
            or _token is not _REPLAY_COMPARISON_TOKEN
        ):
            raise _wrong("/deterministic_replay_comparison")
        probe_record = _exact(probe, FixtureReplayProbeRecord, "/probe")
        key = probe_record.baseline_result.challenge_key
        result_ref = _generator_ref(
            baseline_result_ref,
            GeneratorResultRef,
            challenge_key=key,
            path="/baseline_result_ref",
        )
        event_ref = _owner(
            baseline_source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/baseline_source_event_ref",
        )
        fingerprint_ref = _generator_ref(
            baseline_physical_payload_fingerprint_ref,
            PhysicalPayloadFingerprintRef,
            challenge_key=key,
            path="/baseline_physical_payload_fingerprint_ref",
        )
        case_ref = _top_ref(
            baseline_case_ref,
            CanonicalChallengeCaseRef,
            challenge_key=key,
            path="/baseline_case_ref",
        )
        checked_probe_ref = _generator_ref(
            probe_ref,
            FixtureReplayProbeRef,
            challenge_key=key,
            path="/probe_ref",
        )
        observed_fingerprint_ref = _generator_ref(
            observed_physical_payload_fingerprint_ref,
            PhysicalPayloadFingerprintRef,
            challenge_key=key,
            path="/observed_physical_payload_fingerprint_ref",
        )
        reconstructed_payload_ref = _owner(
            reconstructed_protected_payload_ref,
            "protected_case_payload",
            challenge_key=key,
            path="/reconstructed_protected_payload_ref",
        )
        reconstructed_event_ref = _owner(
            reconstructed_source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/reconstructed_source_event_ref",
        )
        reconstructed_case = _top_ref(
            reconstructed_case_ref,
            CanonicalChallengeCaseRef,
            challenge_key=key,
            path="/reconstructed_case_ref",
        )
        if (
            probe_record.to_ref() != checked_probe_ref
            or probe_record.baseline_result_ref != result_ref
            or probe_record.baseline_result.source_event_ref != event_ref
            or _case_pair_from_result(probe_record.baseline_result).ref != case_ref
            or probe_record.observed_physical_payload_fingerprint_ref
            != observed_fingerprint_ref
            or probe_record.reconstructed_protected_payload_ref
            != reconstructed_payload_ref
            or probe_record.reconstructed_source_event_ref != reconstructed_event_ref
            or probe_record.reconstructed_case_ref != reconstructed_case
        ):
            raise _stale("/deterministic_replay_comparison")
        for name, value in (
            (
                "physical_payload_fingerprint_equal",
                physical_payload_fingerprint_equal,
            ),
            (
                "source_event_bytes_and_ref_equal",
                source_event_bytes_and_ref_equal,
            ),
            ("case_bytes_and_ref_equal", case_bytes_and_ref_equal),
        ):
            if type(value) is not bool:
                raise _wrong(f"/{name}")
        expected_physical = fingerprint_ref == observed_fingerprint_ref
        expected_event = event_ref == reconstructed_event_ref
        expected_case = case_ref == reconstructed_case
        if (
            physical_payload_fingerprint_equal is not expected_physical
            or source_event_bytes_and_ref_equal is not expected_event
            or case_bytes_and_ref_equal is not expected_case
        ):
            raise _stale("/deterministic_replay_comparison")
        object.__setattr__(self, "baseline_result_ref", result_ref)
        object.__setattr__(self, "baseline_source_event_ref", event_ref)
        object.__setattr__(
            self, "baseline_physical_payload_fingerprint_ref", fingerprint_ref
        )
        object.__setattr__(self, "baseline_case_ref", case_ref)
        object.__setattr__(self, "probe", probe_record)
        object.__setattr__(self, "probe_ref", checked_probe_ref)
        object.__setattr__(
            self, "observed_physical_payload_fingerprint_ref", observed_fingerprint_ref
        )
        object.__setattr__(
            self, "reconstructed_protected_payload_ref", reconstructed_payload_ref
        )
        object.__setattr__(
            self, "reconstructed_source_event_ref", reconstructed_event_ref
        )
        object.__setattr__(self, "reconstructed_case_ref", reconstructed_case)
        object.__setattr__(
            self, "physical_payload_fingerprint_equal", expected_physical
        )
        object.__setattr__(self, "source_event_bytes_and_ref_equal", expected_event)
        object.__setattr__(self, "case_bytes_and_ref_equal", expected_case)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> DeterministicReplayComparisonRef:
        from .canonical import _record_ref

        return _record_ref(
            self,
            DeterministicReplayComparisonRef,
            challenge_key=self.baseline_result_ref.challenge_key,
        )  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self) -> object:
        _reject_pickle(type(self).__name__)

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def _new_deterministic_replay_comparison(
    **kwargs: object,
) -> DeterministicReplayComparison:
    return DeterministicReplayComparison(
        **kwargs,
        _token=_REPLAY_COMPARISON_TOKEN,
    )


def compare_fixture_replay(
    *,
    baseline_result: GeneratorResult,
    baseline_result_ref: GeneratorResultRef,
    probe: FixtureReplayProbe,
    probe_ref: FixtureReplayProbeRef,
) -> tuple[DeterministicReplayComparison, DeterministicReplayComparisonRef]:
    """Purely derive three byte/ref equality facts without mutating either input."""

    result = _exact(baseline_result, GeneratorResult, "/baseline_result")
    result_ref = _exact(
        baseline_result_ref,
        GeneratorResultRef,
        "/baseline_result_ref",
    )
    if result.ref != result_ref or result.record.to_ref() != result_ref:
        raise _stale("/baseline_result_ref")
    probe_wrapper = _exact(probe, FixtureReplayProbe, "/probe")
    checked_probe_ref = _exact(probe_ref, FixtureReplayProbeRef, "/probe_ref")
    if (
        probe_wrapper.ref != checked_probe_ref
        or probe_wrapper.record.to_ref() != checked_probe_ref
    ):
        raise _stale("/probe_ref")
    if probe_wrapper.record.baseline_result != result.record:
        raise _stale("/probe/baseline_result")
    case_pair = _case_pair_from_result(result.record)
    if result.artifact is None or result.artifact.case_ref != case_pair.ref:
        raise _incomplete("/baseline_result/artifact")
    payload_facts = _payload_facts_from_result(result.record)
    fingerprint_ref = payload_facts.physical_payload_fingerprint_ref
    event_equal = (
        result.record.source_event_ref
        == probe_wrapper.record.reconstructed_source_event_ref
        and result.record.source_event.canonical_bytes()
        == probe_wrapper.source_event.canonical_bytes()
    )
    case_equal = (
        case_pair.ref == probe_wrapper.record.reconstructed_case_ref
        and result.artifact.case.canonical_bytes()
        == probe_wrapper.case.canonical_bytes()
    )
    comparison = _new_deterministic_replay_comparison(
        baseline_result_ref=result_ref,
        baseline_source_event_ref=result.record.source_event_ref,
        baseline_physical_payload_fingerprint_ref=fingerprint_ref,
        baseline_case_ref=case_pair.ref,
        probe=probe_wrapper.record,
        probe_ref=checked_probe_ref,
        observed_physical_payload_fingerprint_ref=(
            probe_wrapper.record.observed_physical_payload_fingerprint_ref
        ),
        reconstructed_protected_payload_ref=(
            probe_wrapper.record.reconstructed_protected_payload_ref
        ),
        reconstructed_source_event_ref=(
            probe_wrapper.record.reconstructed_source_event_ref
        ),
        reconstructed_case_ref=probe_wrapper.record.reconstructed_case_ref,
        physical_payload_fingerprint_equal=(
            fingerprint_ref
            == probe_wrapper.record.observed_physical_payload_fingerprint_ref
        ),
        source_event_bytes_and_ref_equal=event_equal,
        case_bytes_and_ref_equal=case_equal,
    )
    return comparison, comparison.to_ref()


class ComparisonCorpusAvailability(str, Enum):
    BOUND = "BOUND"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"


class NearDuplicateDecisionKind(str, Enum):
    DISTINCT = "DISTINCT"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"


@final
@dataclass(frozen=True, slots=True, repr=False)
class PostResultDuplicateRequest:
    """Canonical post-result subject and its two admitted failure reasons."""

    challenge_key: ChallengeKey
    subject_result: GeneratorResultRecord
    subject_result_ref: GeneratorResultRef
    case_representation_ref: object
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    corpus_owner_unavailable_reason_ref: object
    near_duplicate_policy_unavailable_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not PostResultDuplicateRequest:
            raise _wrong("/post_result_request")
        key = _challenge(self.challenge_key)
        result = replace(
            _exact(
                self.subject_result,
                GeneratorResultRecord,
                "/subject_result",
            )
        )
        result_ref = _generator_ref(
            self.subject_result_ref,
            GeneratorResultRef,
            challenge_key=key,
            path="/subject_result_ref",
        )
        if result.challenge_key != key or result.to_ref() != result_ref:
            raise _stale("/subject_result_ref")
        case_pair = _case_pair_from_result(result, path="/subject_result")
        representation_ref = _owner(
            self.case_representation_ref,
            "representation",
            challenge_key=key,
            path="/case_representation_ref",
        )
        configuration_ref = _generator_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            challenge_key=key,
            path="/fixture_configuration_ref",
        )
        if (
            result.fixture_configuration_ref != configuration_ref
            or case_pair.record.case_representation_ref != representation_ref
        ):
            raise _stale("/subject_result")
        corpus_reason = _owner(
            self.corpus_owner_unavailable_reason_ref,
            "applicability_reason",
            challenge_key=key,
            path="/corpus_owner_unavailable_reason_ref",
        )
        policy_reason = _owner(
            self.near_duplicate_policy_unavailable_reason_ref,
            "applicability_reason",
            challenge_key=key,
            path="/near_duplicate_policy_unavailable_reason_ref",
        )
        if corpus_reason == policy_reason:
            raise _invalid("/near_duplicate_policy_unavailable_reason_ref")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "subject_result", result)
        object.__setattr__(self, "subject_result_ref", result_ref)
        object.__setattr__(self, "case_representation_ref", representation_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(
            self,
            "corpus_owner_unavailable_reason_ref",
            corpus_reason,
        )
        object.__setattr__(
            self,
            "near_duplicate_policy_unavailable_reason_ref",
            policy_reason,
        )

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class ComparisonCorpusDecision:
    """Exact corpus-owner echo with one closed availability variant."""

    request: PostResultDuplicateRequest
    availability: ComparisonCorpusAvailability
    corpus_results: tuple[RecordRefPair, ...]
    corpus_issuance_ref: object | None
    unavailable_reason_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not ComparisonCorpusDecision:
            raise _wrong("/corpus_decision")
        request = replace(
            _exact(
                self.request,
                PostResultDuplicateRequest,
                "/request",
            )
        )
        key = request.challenge_key
        availability = _exact(
            self.availability,
            ComparisonCorpusAvailability,
            "/availability",
        )
        if type(self.corpus_results) is not tuple:
            raise _wrong("/corpus_results")
        corpus: list[RecordRefPair] = []
        for index, value in enumerate(self.corpus_results):
            pair = _pair(
                value,
                GeneratorResultRecord,
                GeneratorResultRef,
                f"/corpus_results/{index}",
            )
            result = replace(
                _exact(
                    pair.record,
                    GeneratorResultRecord,
                    f"/corpus_results/{index}/record",
                )
            )
            pair = RecordRefPair(result, pair.ref)
            if result.challenge_key != key:
                raise _cross_challenge(f"/corpus_results/{index}")
            if pair.ref == request.subject_result_ref:
                raise _invalid(f"/corpus_results/{index}")
            case_pair = _case_pair_from_result(
                result,
                path=f"/corpus_results/{index}/record",
            )
            if (
                result.fixture_configuration_ref != request.fixture_configuration_ref
                or case_pair.record.case_representation_ref
                != request.case_representation_ref
            ):
                raise _stale(f"/corpus_results/{index}")
            _payload_facts_from_result(
                result,
                path=f"/corpus_results/{index}/record",
            )
            corpus.append(pair)
        corpus_tuple = tuple(corpus)
        if len({item.ref for item in corpus_tuple}) != len(corpus_tuple):
            raise _invalid("/corpus_results")
        if availability is ComparisonCorpusAvailability.BOUND:
            issuance_ref = _owner(
                self.corpus_issuance_ref,
                "authority_evidence",
                challenge_key=key,
                path="/corpus_issuance_ref",
            )
            if self.unavailable_reason_ref is not None:
                raise _invalid("/unavailable_reason_ref")
            unavailable_ref = None
        else:
            if corpus_tuple or self.corpus_issuance_ref is not None:
                raise _invalid("/corpus_results")
            if (
                self.unavailable_reason_ref
                != request.corpus_owner_unavailable_reason_ref
            ):
                raise _stale("/unavailable_reason_ref")
            issuance_ref = None
            unavailable_ref = request.corpus_owner_unavailable_reason_ref
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "availability", availability)
        object.__setattr__(self, "corpus_results", corpus_tuple)
        object.__setattr__(self, "corpus_issuance_ref", issuance_ref)
        object.__setattr__(self, "unavailable_reason_ref", unavailable_ref)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> ComparisonCorpusDecisionRef:
        from .canonical import _record_ref

        return _record_ref(
            self,
            ComparisonCorpusDecisionRef,
            challenge_key=self.request.challenge_key,
        )  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


class ComparisonCorpusAuthority(Protocol):
    """Nominal owner of the protected post-result comparison corpus."""

    def decide_comparison_corpus(
        self,
        request: PostResultDuplicateRequest,
    ) -> ComparisonCorpusDecision:
        """Return one exact corpus decision for the complete request."""


def _comparison_corpus_owner_unavailable(
    request: PostResultDuplicateRequest,
) -> ComparisonCorpusDecision:
    return ComparisonCorpusDecision(
        request=request,
        availability=ComparisonCorpusAvailability.OWNER_UNAVAILABLE,
        corpus_results=(),
        corpus_issuance_ref=None,
        unavailable_reason_ref=request.corpus_owner_unavailable_reason_ref,
    )


def decide_comparison_corpus(
    request: PostResultDuplicateRequest,
    authority: ComparisonCorpusAuthority,
) -> tuple[ComparisonCorpusDecision, ComparisonCorpusDecisionRef]:
    """Call the nominal corpus owner once and fail closed without echoing."""

    checked_request = replace(_exact(request, PostResultDuplicateRequest, "/request"))
    try:
        method = getattr(authority, "decide_comparison_corpus", None)
        if not callable(method):
            raise TypeError("comparison corpus authority method unavailable")
        response = method(checked_request)
        decision = replace(
            _exact(response, ComparisonCorpusDecision, "/corpus_decision")
        )
        if decision.request != checked_request:
            raise _stale("/corpus_decision/request")
        decision_ref = decision.to_ref()
        return decision, decision_ref
    except Exception:  # noqa: BLE001 - sanitize the nominal authority boundary
        decision = _comparison_corpus_owner_unavailable(checked_request)
        return decision, decision.to_ref()


@final
@dataclass(frozen=True, slots=True, repr=False)
class DuplicateComparisonRequest:
    """Exact mechanical case/fingerprint comparison input."""

    subject_case_ref: CanonicalChallengeCaseRef
    subject_physical_payload_fingerprint: PhysicalPayloadFingerprint
    subject_physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef
    corpus_decision: ComparisonCorpusDecision
    corpus_decision_ref: ComparisonCorpusDecisionRef
    corpus_case_refs: tuple[CanonicalChallengeCaseRef, ...]
    corpus_physical_payload_fingerprints: tuple[PhysicalPayloadFingerprint, ...]
    corpus_physical_payload_fingerprint_refs: tuple[PhysicalPayloadFingerprintRef, ...]

    def __post_init__(self) -> None:
        if type(self) is not DuplicateComparisonRequest:
            raise _wrong("/duplicate_comparison_request_binding")
        decision = replace(
            _exact(
                self.corpus_decision,
                ComparisonCorpusDecision,
                "/corpus_decision",
            )
        )
        if decision.availability is not ComparisonCorpusAvailability.BOUND:
            raise _invalid("/corpus_decision")
        key = decision.request.challenge_key
        decision_ref = _generator_ref(
            self.corpus_decision_ref,
            ComparisonCorpusDecisionRef,
            challenge_key=key,
            path="/corpus_decision_ref",
        )
        if decision.to_ref() != decision_ref:
            raise _stale("/corpus_decision_ref")
        subject_case = _top_ref(
            self.subject_case_ref,
            CanonicalChallengeCaseRef,
            challenge_key=key,
            path="/subject_case_ref",
        )
        subject_fingerprint = _exact(
            self.subject_physical_payload_fingerprint,
            PhysicalPayloadFingerprint,
            "/subject_physical_payload_fingerprint",
        )
        checked_subject_fingerprint = _new_physical_payload_fingerprint(
            challenge_key=subject_fingerprint.challenge_key,
            case_representation_ref=subject_fingerprint.case_representation_ref,
            fixture_configuration_ref=subject_fingerprint.fixture_configuration_ref,
            protected_payload_digest=subject_fingerprint.protected_payload_digest,
        )
        if checked_subject_fingerprint != subject_fingerprint:
            raise _stale("/subject_physical_payload_fingerprint")
        subject_fingerprint_ref = _generator_ref(
            self.subject_physical_payload_fingerprint_ref,
            PhysicalPayloadFingerprintRef,
            challenge_key=key,
            path="/subject_physical_payload_fingerprint_ref",
        )
        subject_result = decision.request.subject_result
        subject_case_pair = _case_pair_from_result(
            subject_result,
            path="/corpus_decision/request/subject_result",
        )
        subject_facts = _payload_facts_from_result(
            subject_result,
            path="/corpus_decision/request/subject_result",
        )
        if (
            subject_case_pair.ref != subject_case
            or subject_facts.physical_payload_fingerprint != subject_fingerprint
            or subject_facts.physical_payload_fingerprint_ref != subject_fingerprint_ref
        ):
            raise _stale("/subject_case_ref")
        values = (
            self.corpus_case_refs,
            self.corpus_physical_payload_fingerprints,
            self.corpus_physical_payload_fingerprint_refs,
        )
        if any(type(value) is not tuple for value in values) or any(
            len(value) != len(decision.corpus_results) for value in values
        ):
            raise _invalid("/corpus_case_refs")
        checked_cases: list[CanonicalChallengeCaseRef] = []
        checked_fingerprints: list[PhysicalPayloadFingerprint] = []
        checked_fingerprint_refs: list[PhysicalPayloadFingerprintRef] = []
        for index, pair in enumerate(decision.corpus_results):
            case_pair = _case_pair_from_result(
                pair.record,
                path=f"/corpus_decision/corpus_results/{index}/record",
            )
            facts = _payload_facts_from_result(
                pair.record,
                path=f"/corpus_decision/corpus_results/{index}/record",
            )
            case_ref = _top_ref(
                self.corpus_case_refs[index],
                CanonicalChallengeCaseRef,
                challenge_key=key,
                path=f"/corpus_case_refs/{index}",
            )
            fingerprint = _exact(
                self.corpus_physical_payload_fingerprints[index],
                PhysicalPayloadFingerprint,
                f"/corpus_physical_payload_fingerprints/{index}",
            )
            checked_fingerprint = _new_physical_payload_fingerprint(
                challenge_key=fingerprint.challenge_key,
                case_representation_ref=fingerprint.case_representation_ref,
                fixture_configuration_ref=fingerprint.fixture_configuration_ref,
                protected_payload_digest=fingerprint.protected_payload_digest,
            )
            if checked_fingerprint != fingerprint:
                raise _stale(f"/corpus_physical_payload_fingerprints/{index}")
            fingerprint_ref = _generator_ref(
                self.corpus_physical_payload_fingerprint_refs[index],
                PhysicalPayloadFingerprintRef,
                challenge_key=key,
                path=f"/corpus_physical_payload_fingerprint_refs/{index}",
            )
            if (
                case_pair.ref != case_ref
                or facts.physical_payload_fingerprint != fingerprint
                or facts.physical_payload_fingerprint_ref != fingerprint_ref
            ):
                raise _stale(f"/corpus_case_refs/{index}")
            checked_cases.append(case_ref)
            checked_fingerprints.append(fingerprint)
            checked_fingerprint_refs.append(fingerprint_ref)
        object.__setattr__(self, "subject_case_ref", subject_case)
        object.__setattr__(
            self,
            "subject_physical_payload_fingerprint",
            checked_subject_fingerprint,
        )
        object.__setattr__(
            self,
            "subject_physical_payload_fingerprint_ref",
            subject_fingerprint_ref,
        )
        object.__setattr__(self, "corpus_decision_ref", decision_ref)
        object.__setattr__(self, "corpus_decision", decision)
        object.__setattr__(self, "corpus_case_refs", tuple(checked_cases))
        object.__setattr__(
            self,
            "corpus_physical_payload_fingerprints",
            tuple(
                _new_physical_payload_fingerprint(
                    challenge_key=item.challenge_key,
                    case_representation_ref=item.case_representation_ref,
                    fixture_configuration_ref=item.fixture_configuration_ref,
                    protected_payload_digest=item.protected_payload_digest,
                )
                for item in checked_fingerprints
            ),
        )
        object.__setattr__(
            self,
            "corpus_physical_payload_fingerprint_refs",
            tuple(checked_fingerprint_refs),
        )

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class NearDuplicateRequest:
    """Exact external-policy request; B-03 supplies no nearness rule."""

    post_result_request: PostResultDuplicateRequest
    corpus_decision: ComparisonCorpusDecision
    corpus_decision_ref: ComparisonCorpusDecisionRef
    duplicate_rule_ref: object
    semantic_equivalence_ref: object
    policy_unavailable_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not NearDuplicateRequest:
            raise _wrong("/request")
        request = replace(
            _exact(
                self.post_result_request,
                PostResultDuplicateRequest,
                "/post_result_request",
            )
        )
        decision = replace(
            _exact(
                self.corpus_decision,
                ComparisonCorpusDecision,
                "/corpus_decision",
            )
        )
        key = request.challenge_key
        decision_ref = _generator_ref(
            self.corpus_decision_ref,
            ComparisonCorpusDecisionRef,
            challenge_key=key,
            path="/corpus_decision_ref",
        )
        if (
            decision.availability is not ComparisonCorpusAvailability.BOUND
            or decision.request != request
            or decision.to_ref() != decision_ref
        ):
            raise _stale("/corpus_decision")
        duplicate_rule_ref = _owner(
            self.duplicate_rule_ref,
            "duplicate_rule",
            challenge_key=key,
            path="/duplicate_rule_ref",
        )
        semantic_ref = _owner(
            self.semantic_equivalence_ref,
            "semantic_equivalence",
            challenge_key=key,
            path="/semantic_equivalence_ref",
        )
        if (
            self.policy_unavailable_reason_ref
            != request.near_duplicate_policy_unavailable_reason_ref
        ):
            raise _stale("/policy_unavailable_reason_ref")
        object.__setattr__(self, "post_result_request", request)
        object.__setattr__(self, "corpus_decision", decision)
        object.__setattr__(self, "corpus_decision_ref", decision_ref)
        object.__setattr__(self, "duplicate_rule_ref", duplicate_rule_ref)
        object.__setattr__(self, "semantic_equivalence_ref", semantic_ref)
        object.__setattr__(
            self,
            "policy_unavailable_reason_ref",
            request.near_duplicate_policy_unavailable_reason_ref,
        )

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class NearDuplicateDecision:
    """Closed external semantic-nearness decision echo."""

    request: NearDuplicateRequest
    decision_kind: NearDuplicateDecisionKind
    semantic_equivalence_ref: object | None
    fact_ref: object | None
    audit_evidence_ref: object | None
    duplicate_rule_ref: object | None
    unavailable_reason_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not NearDuplicateDecision:
            raise _wrong("/near_duplicate_decision")
        request = replace(_exact(self.request, NearDuplicateRequest, "/request"))
        kind = _exact(
            self.decision_kind,
            NearDuplicateDecisionKind,
            "/decision_kind",
        )
        key = request.post_result_request.challenge_key
        if kind in {
            NearDuplicateDecisionKind.DISTINCT,
            NearDuplicateDecisionKind.NEAR_DUPLICATE,
        }:
            if self.semantic_equivalence_ref != request.semantic_equivalence_ref:
                raise _stale("/semantic_equivalence_ref")
            fact_ref = _owner(
                self.fact_ref,
                "evidence_artifact",
                challenge_key=key,
                path="/fact_ref",
            )
            audit_ref = _owner(
                self.audit_evidence_ref,
                "audit_evidence",
                challenge_key=key,
                path="/audit_evidence_ref",
            )
            if (
                self.duplicate_rule_ref is not None
                or self.unavailable_reason_ref is not None
            ):
                raise _invalid("/duplicate_rule_ref")
            semantic_ref = request.semantic_equivalence_ref
            duplicate_rule_ref = None
            unavailable_ref = None
        else:
            if (
                self.duplicate_rule_ref != request.duplicate_rule_ref
                or self.semantic_equivalence_ref != request.semantic_equivalence_ref
                or self.unavailable_reason_ref != request.policy_unavailable_reason_ref
            ):
                raise _stale("/unavailable_reason_ref")
            if self.fact_ref is not None or self.audit_evidence_ref is not None:
                raise _invalid("/fact_ref")
            semantic_ref = request.semantic_equivalence_ref
            duplicate_rule_ref = request.duplicate_rule_ref
            unavailable_ref = request.policy_unavailable_reason_ref
            fact_ref = None
            audit_ref = None
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "semantic_equivalence_ref", semantic_ref)
        object.__setattr__(self, "fact_ref", fact_ref)
        object.__setattr__(self, "audit_evidence_ref", audit_ref)
        object.__setattr__(self, "duplicate_rule_ref", duplicate_rule_ref)
        object.__setattr__(self, "unavailable_reason_ref", unavailable_ref)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


class NearDuplicatePolicyAuthority(Protocol):
    """Nominal owner of semantic near-duplicate policy decisions."""

    def decide_near_duplicate(
        self,
        request: NearDuplicateRequest,
    ) -> NearDuplicateDecision:
        """Return one exact policy decision for the complete request."""


def _near_duplicate_policy_unavailable(
    request: NearDuplicateRequest,
) -> NearDuplicateDecision:
    return NearDuplicateDecision(
        request=request,
        decision_kind=NearDuplicateDecisionKind.POLICY_UNAVAILABLE,
        semantic_equivalence_ref=request.semantic_equivalence_ref,
        fact_ref=None,
        audit_evidence_ref=None,
        duplicate_rule_ref=request.duplicate_rule_ref,
        unavailable_reason_ref=request.policy_unavailable_reason_ref,
    )


def decide_near_duplicate(
    request: NearDuplicateRequest,
    authority: NearDuplicatePolicyAuthority,
) -> NearDuplicateDecision:
    """Call the nominal policy owner once and fail closed without echoing."""

    checked_request = replace(_exact(request, NearDuplicateRequest, "/request"))
    try:
        method = getattr(authority, "decide_near_duplicate", None)
        if not callable(method):
            raise TypeError("near-duplicate policy authority method unavailable")
        response = method(checked_request)
        decision = replace(
            _exact(response, NearDuplicateDecision, "/near_duplicate_decision")
        )
        if decision.request != checked_request:
            raise _stale("/near_duplicate_decision/request")
        return decision
    except Exception:  # noqa: BLE001 - sanitize the nominal authority boundary
        return _near_duplicate_policy_unavailable(checked_request)


@final
@dataclass(frozen=True, slots=True, repr=False)
class DuplicateConformanceFacts:
    """Post-result duplicate facts that can never mutate the subject result."""

    challenge_key: ChallengeKey
    post_result_request: PostResultDuplicateRequest
    corpus_decision: ComparisonCorpusDecision
    corpus_decision_ref: ComparisonCorpusDecisionRef
    duplicate_comparison_request_binding: ApplicabilityBinding[
        DuplicateComparisonRequest
    ]
    canonical_case_duplicate_binding: ApplicabilityBinding[bool]
    physical_instance_collision_binding: ApplicabilityBinding[bool]
    near_duplicate_decision_binding: ApplicabilityBinding[NearDuplicateDecision]

    def __post_init__(self) -> None:
        if type(self) is not DuplicateConformanceFacts:
            raise _wrong("/duplicate_conformance_facts")
        key = _challenge(self.challenge_key)
        request = replace(
            _exact(
                self.post_result_request,
                PostResultDuplicateRequest,
                "/post_result_request",
            )
        )
        decision = replace(
            _exact(
                self.corpus_decision,
                ComparisonCorpusDecision,
                "/corpus_decision",
            )
        )
        decision_ref = _generator_ref(
            self.corpus_decision_ref,
            ComparisonCorpusDecisionRef,
            challenge_key=key,
            path="/corpus_decision_ref",
        )
        if (
            request.challenge_key != key
            or decision.request != request
            or decision.to_ref() != decision_ref
        ):
            raise _stale("/corpus_decision")
        comparison_binding = _applicability(
            self.duplicate_comparison_request_binding,
            DuplicateComparisonRequest,
            challenge_key=key,
            path="/duplicate_comparison_request_binding",
        )
        canonical_binding = _applicability(
            self.canonical_case_duplicate_binding,
            bool,
            challenge_key=key,
            path="/canonical_case_duplicate_binding",
        )
        physical_binding = _applicability(
            self.physical_instance_collision_binding,
            bool,
            challenge_key=key,
            path="/physical_instance_collision_binding",
        )
        near_binding = _applicability(
            self.near_duplicate_decision_binding,
            NearDuplicateDecision,
            challenge_key=key,
            path="/near_duplicate_decision_binding",
        )
        if comparison_binding.is_bound:
            comparison_binding = ApplicabilityBinding.bound(
                replace(
                    _exact(
                        comparison_binding.value,
                        DuplicateComparisonRequest,
                        "/duplicate_comparison_request_binding/value",
                    )
                )
            )
        else:
            comparison_binding = ApplicabilityBinding.not_applicable(
                _owner(
                    comparison_binding.value,
                    "applicability_reason",
                    challenge_key=key,
                    path="/duplicate_comparison_request_binding/value",
                )
            )
        rebuilt_boolean_bindings: list[ApplicabilityBinding] = []
        for path, binding in (
            ("/canonical_case_duplicate_binding", canonical_binding),
            ("/physical_instance_collision_binding", physical_binding),
        ):
            if binding.is_bound:
                rebuilt_boolean_bindings.append(
                    ApplicabilityBinding.bound(_exact(binding.value, bool, path))
                )
            else:
                rebuilt_boolean_bindings.append(
                    ApplicabilityBinding.not_applicable(
                        _owner(
                            binding.value,
                            "applicability_reason",
                            challenge_key=key,
                            path=f"{path}/value",
                        )
                    )
                )
        canonical_binding, physical_binding = rebuilt_boolean_bindings
        if near_binding.is_bound:
            near_binding = ApplicabilityBinding.bound(
                replace(
                    _exact(
                        near_binding.value,
                        NearDuplicateDecision,
                        "/near_duplicate_decision_binding/value",
                    )
                )
            )
        else:
            near_binding = ApplicabilityBinding.not_applicable(
                _owner(
                    near_binding.value,
                    "applicability_reason",
                    challenge_key=key,
                    path="/near_duplicate_decision_binding/value",
                )
            )
        bindings = (
            comparison_binding,
            canonical_binding,
            physical_binding,
            near_binding,
        )
        if decision.availability is ComparisonCorpusAvailability.OWNER_UNAVAILABLE:
            reason = request.corpus_owner_unavailable_reason_ref
            if any(binding.is_bound or binding.value != reason for binding in bindings):
                raise _stale("/duplicate_comparison_request_binding")
        else:
            if not all(binding.is_bound for binding in bindings):
                raise _incomplete("/duplicate_comparison_request_binding")
            comparison = comparison_binding.value
            if (
                comparison.corpus_decision != decision
                or comparison.corpus_decision_ref != decision_ref
            ):
                raise _stale("/duplicate_comparison_request_binding")
            expected_case_duplicate = any(
                item == comparison.subject_case_ref
                for item in comparison.corpus_case_refs
            )
            expected_physical_collision = any(
                item == comparison.subject_physical_payload_fingerprint_ref
                for item in comparison.corpus_physical_payload_fingerprint_refs
            )
            if (
                canonical_binding.value is not expected_case_duplicate
                or physical_binding.value is not expected_physical_collision
                or near_binding.value.request.post_result_request != request
                or near_binding.value.request.corpus_decision != decision
                or near_binding.value.request.corpus_decision_ref != decision_ref
            ):
                raise _stale("/canonical_case_duplicate_binding")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "post_result_request", request)
        object.__setattr__(self, "corpus_decision", decision)
        object.__setattr__(self, "corpus_decision_ref", decision_ref)
        object.__setattr__(
            self,
            "duplicate_comparison_request_binding",
            comparison_binding,
        )
        object.__setattr__(
            self,
            "canonical_case_duplicate_binding",
            canonical_binding,
        )
        object.__setattr__(
            self,
            "physical_instance_collision_binding",
            physical_binding,
        )
        object.__setattr__(
            self,
            "near_duplicate_decision_binding",
            near_binding,
        )

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> DuplicateConformanceFactsRef:
        from .canonical import _record_ref

        return _record_ref(self, DuplicateConformanceFactsRef)  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def build_post_result_duplicate_request(
    *,
    subject_result: GeneratorResult,
    corpus_owner_unavailable_reason_ref: object,
    near_duplicate_policy_unavailable_reason_ref: object,
) -> PostResultDuplicateRequest:
    """Derive the canonical subject request from one complete result wrapper."""

    result = _exact(subject_result, GeneratorResult, "/subject_result")
    case_pair = _case_pair_from_result(result.record, path="/subject_result/record")
    if result.artifact is None or result.artifact.case_ref != case_pair.ref:
        raise _incomplete("/subject_result/artifact")
    _payload_facts_from_result(result.record, path="/subject_result/record")
    return PostResultDuplicateRequest(
        challenge_key=result.record.challenge_key,
        subject_result=result.record,
        subject_result_ref=result.ref,
        case_representation_ref=case_pair.record.case_representation_ref,
        fixture_configuration_ref=result.record.fixture_configuration_ref,
        corpus_owner_unavailable_reason_ref=corpus_owner_unavailable_reason_ref,
        near_duplicate_policy_unavailable_reason_ref=(
            near_duplicate_policy_unavailable_reason_ref
        ),
    )


def build_duplicate_comparison_request(
    *,
    corpus_decision: ComparisonCorpusDecision,
    corpus_decision_ref: ComparisonCorpusDecisionRef,
) -> DuplicateComparisonRequest:
    """Exact-recompute every case and physical-fingerprint comparison input."""

    decision = _exact(
        corpus_decision,
        ComparisonCorpusDecision,
        "/corpus_decision",
    )
    if decision.availability is not ComparisonCorpusAvailability.BOUND:
        raise _invalid("/corpus_decision")
    subject_result = decision.request.subject_result
    subject_case = _case_pair_from_result(
        subject_result,
        path="/corpus_decision/request/subject_result",
    )
    subject_facts = _payload_facts_from_result(
        subject_result,
        path="/corpus_decision/request/subject_result",
    )
    corpus_cases: list[CanonicalChallengeCaseRef] = []
    corpus_fingerprints: list[PhysicalPayloadFingerprint] = []
    corpus_fingerprint_refs: list[PhysicalPayloadFingerprintRef] = []
    for index, pair in enumerate(decision.corpus_results):
        corpus_cases.append(
            _case_pair_from_result(
                pair.record,
                path=f"/corpus_decision/corpus_results/{index}/record",
            ).ref
        )
        facts = _payload_facts_from_result(
            pair.record,
            path=f"/corpus_decision/corpus_results/{index}/record",
        )
        corpus_fingerprints.append(facts.physical_payload_fingerprint)
        corpus_fingerprint_refs.append(facts.physical_payload_fingerprint_ref)
    return DuplicateComparisonRequest(
        subject_case_ref=subject_case.ref,
        subject_physical_payload_fingerprint=(
            subject_facts.physical_payload_fingerprint
        ),
        subject_physical_payload_fingerprint_ref=(
            subject_facts.physical_payload_fingerprint_ref
        ),
        corpus_decision=decision,
        corpus_decision_ref=corpus_decision_ref,
        corpus_case_refs=tuple(corpus_cases),
        corpus_physical_payload_fingerprints=tuple(corpus_fingerprints),
        corpus_physical_payload_fingerprint_refs=tuple(corpus_fingerprint_refs),
    )


def build_near_duplicate_request(
    *,
    post_result_request: PostResultDuplicateRequest,
    corpus_decision: ComparisonCorpusDecision,
    corpus_decision_ref: ComparisonCorpusDecisionRef,
    duplicate_rule_ref: object,
    semantic_equivalence_ref: object,
) -> NearDuplicateRequest:
    return NearDuplicateRequest(
        post_result_request=post_result_request,
        corpus_decision=corpus_decision,
        corpus_decision_ref=corpus_decision_ref,
        duplicate_rule_ref=duplicate_rule_ref,
        semantic_equivalence_ref=semantic_equivalence_ref,
        policy_unavailable_reason_ref=(
            post_result_request.near_duplicate_policy_unavailable_reason_ref
        ),
    )


def build_duplicate_conformance_facts(
    *,
    post_result_request: PostResultDuplicateRequest,
    corpus_decision: ComparisonCorpusDecision,
    corpus_decision_ref: ComparisonCorpusDecisionRef,
    near_duplicate_decision: NearDuplicateDecision | None,
) -> tuple[DuplicateConformanceFacts, DuplicateConformanceFactsRef]:
    """Derive mechanical duplicate facts without accepting caller Booleans."""

    request = _exact(
        post_result_request,
        PostResultDuplicateRequest,
        "/post_result_request",
    )
    decision = _exact(
        corpus_decision,
        ComparisonCorpusDecision,
        "/corpus_decision",
    )
    if decision.request != request:
        raise _stale("/corpus_decision/request")
    if decision.availability is ComparisonCorpusAvailability.OWNER_UNAVAILABLE:
        if near_duplicate_decision is not None:
            raise _invalid("/near_duplicate_decision")
        reason = request.corpus_owner_unavailable_reason_ref
        comparison_binding = ApplicabilityBinding.not_applicable(reason)
        canonical_binding = ApplicabilityBinding.not_applicable(reason)
        physical_binding = ApplicabilityBinding.not_applicable(reason)
        near_binding = ApplicabilityBinding.not_applicable(reason)
    else:
        near = _exact(
            near_duplicate_decision,
            NearDuplicateDecision,
            "/near_duplicate_decision",
        )
        comparison = build_duplicate_comparison_request(
            corpus_decision=decision,
            corpus_decision_ref=corpus_decision_ref,
        )
        comparison_binding = ApplicabilityBinding.bound(comparison)
        canonical_binding = ApplicabilityBinding.bound(
            any(
                item == comparison.subject_case_ref
                for item in comparison.corpus_case_refs
            )
        )
        physical_binding = ApplicabilityBinding.bound(
            any(
                item == comparison.subject_physical_payload_fingerprint_ref
                for item in comparison.corpus_physical_payload_fingerprint_refs
            )
        )
        near_binding = ApplicabilityBinding.bound(near)
    facts = DuplicateConformanceFacts(
        challenge_key=request.challenge_key,
        post_result_request=request,
        corpus_decision=decision,
        corpus_decision_ref=corpus_decision_ref,
        duplicate_comparison_request_binding=comparison_binding,
        canonical_case_duplicate_binding=canonical_binding,
        physical_instance_collision_binding=physical_binding,
        near_duplicate_decision_binding=near_binding,
    )
    return facts, facts.to_ref()


class ExternalDistributionFactKind(str, Enum):
    REALIZED_STRATUM = "REALIZED_STRATUM"
    TAIL_ALLOCATION = "TAIL_ALLOCATION"
    MARGINAL = "MARGINAL"
    JOINT = "JOINT"
    CONDITIONAL = "CONDITIONAL"
    CENSORING_BY_CAUSE = "CENSORING_BY_CAUSE"
    CENSORING_BY_STRATUM = "CENSORING_BY_STRATUM"


class ExternalFactAvailabilityKind(str, Enum):
    BOUND = "BOUND"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"


def _result_pairs(
    value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> tuple[RecordRefPair, ...]:
    if type(value) is not tuple:
        raise _wrong(path)
    result: list[RecordRefPair] = []
    for index, item in enumerate(value):
        pair = _pair(
            item,
            GeneratorResultRecord,
            GeneratorResultRef,
            f"{path}/{index}",
        )
        record = replace(
            _exact(
                pair.record,
                GeneratorResultRecord,
                f"{path}/{index}/record",
            )
        )
        pair = RecordRefPair(record, pair.ref)
        if record.challenge_key != challenge_key:
            raise _cross_challenge(f"{path}/{index}")
        _case_pair_from_result(record, path=f"{path}/{index}/record")
        result.append(pair)
    if len({item.ref for item in result}) != len(result):
        raise _invalid(path)
    return tuple(result)


def _intended_unit_pairs(
    value: object,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> tuple[RecordRefPair, ...]:
    if type(value) is not tuple or not value:
        raise _wrong(path)
    result: list[RecordRefPair] = []
    for index, item in enumerate(value):
        pair = _pair(
            item,
            IntendedUnitAccounting,
            IntendedUnitAccountingRef,
            f"{path}/{index}",
        )
        record = replace(
            _exact(
                pair.record,
                IntendedUnitAccounting,
                f"{path}/{index}/record",
            )
        )
        pair = RecordRefPair(record, pair.ref)
        if record.challenge_key != challenge_key:
            raise _cross_challenge(f"{path}/{index}")
        result.append(pair)
    if len({item.ref for item in result}) != len(result):
        raise _invalid(path)
    return tuple(result)


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExternalDistributionFactRequest:
    """Complete post-accounting corpus for one externally owned fact kind."""

    challenge_key: ChallengeKey
    result_pairs: tuple[RecordRefPair, ...]
    intended_unit_pairs: tuple[RecordRefPair, ...]
    accounting_summary: GenerationAccountingSummary
    accounting_summary_ref: GenerationAccountingSummaryRef
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    requested_fact_kind: ExternalDistributionFactKind
    statistics_objective_ref: object
    owner_unavailable_reason_ref: object

    def __post_init__(self) -> None:
        if type(self) is not ExternalDistributionFactRequest:
            raise _wrong("/request")
        key = _challenge(self.challenge_key)
        results = _result_pairs(
            self.result_pairs,
            challenge_key=key,
            path="/result_pairs",
        )
        units = _intended_unit_pairs(
            self.intended_unit_pairs,
            challenge_key=key,
            path="/intended_unit_pairs",
        )
        summary = replace(
            _exact(
                self.accounting_summary,
                GenerationAccountingSummary,
                "/accounting_summary",
            )
        )
        summary_ref = _generator_ref(
            self.accounting_summary_ref,
            GenerationAccountingSummaryRef,
            challenge_key=key,
            path="/accounting_summary_ref",
        )
        recomputed_summary, recomputed_summary_ref = (
            build_generation_accounting_summary(units)
        )
        if (
            summary != recomputed_summary
            or summary_ref != recomputed_summary_ref
            or summary.to_ref() != summary_ref
        ):
            raise _stale("/accounting_summary")
        plan_ref = _top_ref(
            self.sampling_plan_ref,
            SamplingPlanRef,
            challenge_key=key,
            path="/sampling_plan_ref",
        )
        primary_ref = _top_ref(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/primary_population_ref",
        )
        selection_ref = _top_ref(
            self.selection_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/selection_population_ref",
        )
        if any(
            (
                unit.record.sampling_plan_ref,
                unit.record.primary_population_ref,
                unit.record.selection_population_ref,
            )
            != (plan_ref, primary_ref, selection_ref)
            for unit in units
        ):
            raise _stale("/intended_unit_pairs")
        expected_units = tuple(
            unit
            for unit in units
            if unit.record.realized_outcome
            in {
                GeneratorOutcomeKind.VALID_GENERATED,
                GeneratorOutcomeKind.CENSORED_CASE,
            }
        )
        if len(results) != len(expected_units):
            raise _incomplete("/result_pairs")
        for index, (result_pair, unit_pair) in enumerate(
            zip(results, expected_units, strict=True)
        ):
            result = result_pair.record
            unit = unit_pair.record
            final_attempt_pair = unit.attempt_record_pairs[-1]
            case_pair = _case_pair_from_result(
                result,
                path=f"/result_pairs/{index}/record",
            )
            if (
                result.attempt_record != final_attempt_pair.record
                or result.attempt_record_ref != final_attempt_pair.ref
                or result.outcome_kind is not unit.realized_outcome
                or case_pair.ref != unit.realized_case_ref
                or result.sampling_plan_ref != plan_ref
                or result.primary_population_ref != primary_ref
                or result.selection_population_ref != selection_ref
            ):
                raise _stale(f"/result_pairs/{index}")
        fact_kind = _exact(
            self.requested_fact_kind,
            ExternalDistributionFactKind,
            "/requested_fact_kind",
        )
        objective_ref = _owner(
            self.statistics_objective_ref,
            "statistics_objective",
            challenge_key=key,
            path="/statistics_objective_ref",
        )
        unavailable_ref = _owner(
            self.owner_unavailable_reason_ref,
            "applicability_reason",
            challenge_key=key,
            path="/owner_unavailable_reason_ref",
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "result_pairs", results)
        object.__setattr__(self, "intended_unit_pairs", units)
        object.__setattr__(self, "accounting_summary", summary)
        object.__setattr__(self, "accounting_summary_ref", summary_ref)
        object.__setattr__(self, "sampling_plan_ref", plan_ref)
        object.__setattr__(self, "primary_population_ref", primary_ref)
        object.__setattr__(self, "selection_population_ref", selection_ref)
        object.__setattr__(self, "requested_fact_kind", fact_kind)
        object.__setattr__(self, "statistics_objective_ref", objective_ref)
        object.__setattr__(self, "owner_unavailable_reason_ref", unavailable_ref)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExternalFactAvailability:
    """One closed bound or owner-unavailable external-fact payload."""

    availability: ExternalFactAvailabilityKind
    fact_kind: ExternalDistributionFactKind | None
    statistics_objective_ref: object | None
    fact_ref: object | None
    audit_evidence_ref: object | None
    unavailable_reason_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not ExternalFactAvailability:
            raise _wrong("/availability")
        availability = _exact(
            self.availability,
            ExternalFactAvailabilityKind,
            "/availability",
        )
        if availability is ExternalFactAvailabilityKind.BOUND:
            fact_kind = _exact(
                self.fact_kind,
                ExternalDistributionFactKind,
                "/fact_kind",
            )
            if (
                self.statistics_objective_ref is not None
                or self.unavailable_reason_ref is not None
            ):
                raise _invalid("/statistics_objective_ref")
            fact_ref = require_owner_ref(self.fact_ref, "evidence_artifact")
            audit_ref = require_owner_ref(self.audit_evidence_ref, "audit_evidence")
            objective_ref = None
            unavailable_ref = None
        else:
            if (
                self.fact_kind is not None
                or self.fact_ref is not None
                or self.audit_evidence_ref is not None
            ):
                raise _invalid("/fact_ref")
            objective_ref = require_owner_ref(
                self.statistics_objective_ref,
                "statistics_objective",
            )
            unavailable_ref = require_owner_ref(
                self.unavailable_reason_ref,
                "applicability_reason",
            )
            fact_kind = None
            fact_ref = None
            audit_ref = None
        object.__setattr__(self, "fact_kind", fact_kind)
        object.__setattr__(self, "statistics_objective_ref", objective_ref)
        object.__setattr__(self, "fact_ref", fact_ref)
        object.__setattr__(self, "audit_evidence_ref", audit_ref)
        object.__setattr__(self, "unavailable_reason_ref", unavailable_ref)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExternalDistributionFactDecision:
    """Exact external owner echo and closed availability."""

    request: ExternalDistributionFactRequest
    availability: ExternalFactAvailability

    def __post_init__(self) -> None:
        if type(self) is not ExternalDistributionFactDecision:
            raise _wrong("/decisions")
        request = replace(
            _exact(
                self.request,
                ExternalDistributionFactRequest,
                "/request",
            )
        )
        availability = replace(
            _exact(
                self.availability,
                ExternalFactAvailability,
                "/availability",
            )
        )
        key = request.challenge_key
        if availability.availability is ExternalFactAvailabilityKind.BOUND:
            if availability.fact_kind is not request.requested_fact_kind:
                raise _stale("/availability/fact_kind")
            for path, value, kind in (
                ("/availability/fact_ref", availability.fact_ref, "evidence_artifact"),
                (
                    "/availability/audit_evidence_ref",
                    availability.audit_evidence_ref,
                    "audit_evidence",
                ),
            ):
                _owner(value, kind, challenge_key=key, path=path)
        else:
            if (
                availability.statistics_objective_ref
                != request.statistics_objective_ref
                or availability.unavailable_reason_ref
                != request.owner_unavailable_reason_ref
            ):
                raise _stale("/availability/unavailable_reason_ref")
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "availability", availability)

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


class ExternalDistributionFactAuthority(Protocol):
    """Nominal owner of one requested protected distribution fact."""

    def decide_external_distribution_fact(
        self,
        request: ExternalDistributionFactRequest,
    ) -> ExternalDistributionFactDecision:
        """Return one exact fact decision for the complete request."""


def _external_distribution_fact_owner_unavailable(
    request: ExternalDistributionFactRequest,
) -> ExternalDistributionFactDecision:
    return ExternalDistributionFactDecision(
        request=request,
        availability=ExternalFactAvailability(
            availability=ExternalFactAvailabilityKind.OWNER_UNAVAILABLE,
            fact_kind=None,
            statistics_objective_ref=request.statistics_objective_ref,
            fact_ref=None,
            audit_evidence_ref=None,
            unavailable_reason_ref=request.owner_unavailable_reason_ref,
        ),
    )


def decide_external_distribution_fact(
    request: ExternalDistributionFactRequest,
    authority: ExternalDistributionFactAuthority,
) -> ExternalDistributionFactDecision:
    """Call the nominal fact owner once and fail closed without echoing."""

    checked_request = replace(
        _exact(request, ExternalDistributionFactRequest, "/request")
    )
    try:
        method = getattr(authority, "decide_external_distribution_fact", None)
        if not callable(method):
            raise TypeError("external fact authority method unavailable")
        response = _exact(
            method(checked_request),
            ExternalDistributionFactDecision,
            "/external_distribution_fact_decision",
        )
        availability = replace(
            _exact(
                response.availability,
                ExternalFactAvailability,
                "/external_distribution_fact_decision/availability",
            )
        )
        decision = replace(response, availability=availability)
        if decision.request != checked_request:
            raise _stale("/external_distribution_fact_decision/request")
        return decision
    except Exception:  # noqa: BLE001 - sanitize the nominal authority boundary
        return _external_distribution_fact_owner_unavailable(checked_request)


def _external_decision_key(
    decision: ExternalDistributionFactDecision,
) -> tuple[bytes, bytes]:
    request = decision.request
    return (
        encode_value(CanonicalText(request.requested_fact_kind.value)),
        encode_value(owner_ref_to_canonical(request.statistics_objective_ref)),
    )


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExternalDistributionFactSet:
    """Canonical, complete set of exact external distribution decisions."""

    challenge_key: ChallengeKey
    result_pairs: tuple[RecordRefPair, ...]
    intended_unit_pairs: tuple[RecordRefPair, ...]
    accounting_summary: GenerationAccountingSummary
    accounting_summary_ref: GenerationAccountingSummaryRef
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    decisions: tuple[ExternalDistributionFactDecision, ...]

    def __post_init__(self) -> None:
        if type(self) is not ExternalDistributionFactSet:
            raise _wrong("/external_distribution_fact_set")
        key = _challenge(self.challenge_key)
        if type(self.decisions) is not tuple or not self.decisions:
            raise _wrong("/decisions")
        decisions = tuple(
            replace(
                _exact(
                    value,
                    ExternalDistributionFactDecision,
                    f"/decisions/{index}",
                )
            )
            for index, value in enumerate(self.decisions)
        )
        keys = tuple(_external_decision_key(item) for item in decisions)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise _invalid("/decisions")
        common = (
            self.result_pairs,
            self.intended_unit_pairs,
            self.accounting_summary,
            self.accounting_summary_ref,
            self.sampling_plan_ref,
            self.primary_population_ref,
            self.selection_population_ref,
        )
        for index, decision in enumerate(decisions):
            request = decision.request
            observed = (
                request.result_pairs,
                request.intended_unit_pairs,
                request.accounting_summary,
                request.accounting_summary_ref,
                request.sampling_plan_ref,
                request.primary_population_ref,
                request.selection_population_ref,
            )
            if request.challenge_key != key or observed != common:
                raise _stale(f"/decisions/{index}/request")
        first = decisions[0].request
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "result_pairs", first.result_pairs)
        object.__setattr__(self, "intended_unit_pairs", first.intended_unit_pairs)
        object.__setattr__(self, "accounting_summary", first.accounting_summary)
        object.__setattr__(
            self,
            "accounting_summary_ref",
            first.accounting_summary_ref,
        )
        object.__setattr__(self, "sampling_plan_ref", first.sampling_plan_ref)
        object.__setattr__(self, "primary_population_ref", first.primary_population_ref)
        object.__setattr__(
            self,
            "selection_population_ref",
            first.selection_population_ref,
        )
        object.__setattr__(self, "decisions", decisions)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> ExternalDistributionFactSetRef:
        from .canonical import _record_ref

        return _record_ref(self, ExternalDistributionFactSetRef)  # type: ignore[return-value]

    def __repr__(self) -> str:
        return _redacted(type(self).__name__)

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        _reject_pickle(type(self).__name__)


def build_external_distribution_fact_request(
    *,
    result_pairs: tuple[RecordRefPair, ...],
    intended_unit_pairs: tuple[RecordRefPair, ...],
    accounting_summary: GenerationAccountingSummary,
    accounting_summary_ref: GenerationAccountingSummaryRef,
    requested_fact_kind: ExternalDistributionFactKind,
    statistics_objective_ref: object,
    owner_unavailable_reason_ref: object,
) -> ExternalDistributionFactRequest:
    """Build one complete request without caller-supplied common identities."""

    summary = replace(
        _exact(
            accounting_summary,
            GenerationAccountingSummary,
            "/accounting_summary",
        )
    )
    units = _intended_unit_pairs(
        intended_unit_pairs,
        challenge_key=summary.challenge_key,
        path="/intended_unit_pairs",
    )
    results = _result_pairs(
        result_pairs,
        challenge_key=summary.challenge_key,
        path="/result_pairs",
    )
    first_unit = units[0].record
    return ExternalDistributionFactRequest(
        challenge_key=summary.challenge_key,
        result_pairs=results,
        intended_unit_pairs=units,
        accounting_summary=summary,
        accounting_summary_ref=accounting_summary_ref,
        sampling_plan_ref=first_unit.sampling_plan_ref,
        primary_population_ref=first_unit.primary_population_ref,
        selection_population_ref=first_unit.selection_population_ref,
        requested_fact_kind=requested_fact_kind,
        statistics_objective_ref=statistics_objective_ref,
        owner_unavailable_reason_ref=owner_unavailable_reason_ref,
    )


def build_external_distribution_fact_set(
    decisions: tuple[ExternalDistributionFactDecision, ...],
) -> tuple[ExternalDistributionFactSet, ExternalDistributionFactSetRef]:
    """Canonicalize unique external decisions by exact fact/objective keys."""

    if type(decisions) is not tuple or not decisions:
        raise _wrong("/decisions")
    checked = tuple(
        replace(
            _exact(
                decision,
                ExternalDistributionFactDecision,
                f"/decisions/{index}",
            )
        )
        for index, decision in enumerate(decisions)
    )
    ordered = tuple(sorted(checked, key=_external_decision_key))
    first = ordered[0].request
    fact_set = ExternalDistributionFactSet(
        challenge_key=first.challenge_key,
        result_pairs=first.result_pairs,
        intended_unit_pairs=first.intended_unit_pairs,
        accounting_summary=first.accounting_summary,
        accounting_summary_ref=first.accounting_summary_ref,
        sampling_plan_ref=first.sampling_plan_ref,
        primary_population_ref=first.primary_population_ref,
        selection_population_ref=first.selection_population_ref,
        decisions=ordered,
    )
    return fact_set, fact_set.to_ref()


# Closed canonical registration for the implemented conformance records.
from .canonical import (
    _BOOL,
    _CHALLENGE_KEY,
    _REPLAY_REF,
    _enum,
    _nested,
    _optional,
    _record,
    _register_canonical_type,
    _register_nested_canonical_type,
    _tuple_of,
)
from .canonical import (
    _applicability as _applicability_codec,
)
from .canonical import (
    _generator_ref as _generator_ref_codec,
)
from .canonical import (
    _owner as _owner_codec,
)
from .canonical import (
    _top_ref as _top_ref_codec,
)

_register_nested_canonical_type(
    ReplayIdentityFacts,
    record_type="replay_identity_facts",
    fields=(
        ("request_identity", _record(GeneratorRequestIdentity)),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("replay_ref", _REPLAY_REF),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref_codec(GeneratorEnvironmentRef)),
        (
            "fixture_configuration_ref",
            _generator_ref_codec(BurgersFixtureConfigurationRef),
        ),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("materialization_state", _enum(SourceMaterializationState)),
        (
            "payload_facts_binding",
            _applicability_codec(_nested(FixturePayloadFacts)),
        ),
        (
            "constructed_case_facts_binding",
            _applicability_codec(_nested(ValidatedCaseFacts)),
        ),
    ),
)

_register_canonical_type(
    GeneratorConformanceFacts,
    object_kind="generator_conformance_facts",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_identity", _record(GeneratorRequestIdentity)),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref_codec(GeneratorEnvironmentRef)),
        (
            "fixture_configuration_ref",
            _generator_ref_codec(BurgersFixtureConfigurationRef),
        ),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("terminal_stage", _enum(GeneratorTerminalStage)),
        (
            "payload_facts_binding",
            _applicability_codec(_nested(FixturePayloadFacts)),
        ),
        ("support_decision_binding", _nested(RecordRefBinding)),
        (
            "validated_case_facts_binding",
            _applicability_codec(_nested(ValidatedCaseFacts)),
        ),
        ("replay_identity_facts", _nested(ReplayIdentityFacts)),
    ),
)

_register_canonical_type(
    FixtureReplayProbeRecord,
    object_kind="fixture_replay_probe",
    fields=(
        ("baseline_result", _record(GeneratorResultRecord)),
        ("baseline_result_ref", _generator_ref_codec(GeneratorResultRef)),
        ("baseline_request_identity", _record(GeneratorRequestIdentity)),
        ("baseline_request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("replay_ref", _REPLAY_REF),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref_codec(GeneratorEnvironmentRef)),
        (
            "fixture_configuration_ref",
            _generator_ref_codec(BurgersFixtureConfigurationRef),
        ),
        ("role_binding", _nested(GenerationRoleBinding)),
        (
            "observed_physical_payload_fingerprint",
            _record(PhysicalPayloadFingerprint),
        ),
        (
            "observed_physical_payload_fingerprint_ref",
            _generator_ref_codec(PhysicalPayloadFingerprintRef),
        ),
        (
            "reconstructed_protected_payload_ref",
            _owner_codec("protected_case_payload"),
        ),
        ("reconstructed_source_event_ref", _owner_codec("generation_event")),
        (
            "reconstructed_case_ref",
            _top_ref_codec(CanonicalChallengeCaseRef),
        ),
    ),
    builder=_new_fixture_replay_probe_record,
)

_register_canonical_type(
    DeterministicReplayComparison,
    object_kind="deterministic_replay_comparison",
    fields=(
        ("baseline_result_ref", _generator_ref_codec(GeneratorResultRef)),
        ("baseline_source_event_ref", _owner_codec("generation_event")),
        (
            "baseline_physical_payload_fingerprint_ref",
            _generator_ref_codec(PhysicalPayloadFingerprintRef),
        ),
        ("baseline_case_ref", _top_ref_codec(CanonicalChallengeCaseRef)),
        ("probe", _record(FixtureReplayProbeRecord)),
        ("probe_ref", _generator_ref_codec(FixtureReplayProbeRef)),
        (
            "observed_physical_payload_fingerprint_ref",
            _generator_ref_codec(PhysicalPayloadFingerprintRef),
        ),
        (
            "reconstructed_protected_payload_ref",
            _owner_codec("protected_case_payload"),
        ),
        ("reconstructed_source_event_ref", _owner_codec("generation_event")),
        (
            "reconstructed_case_ref",
            _top_ref_codec(CanonicalChallengeCaseRef),
        ),
        ("physical_payload_fingerprint_equal", _BOOL),
        ("source_event_bytes_and_ref_equal", _BOOL),
        ("case_bytes_and_ref_equal", _BOOL),
    ),
    builder=_new_deterministic_replay_comparison,
)

_register_nested_canonical_type(
    PostResultDuplicateRequest,
    record_type="post_result_duplicate_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("subject_result", _record(GeneratorResultRecord)),
        ("subject_result_ref", _generator_ref_codec(GeneratorResultRef)),
        ("case_representation_ref", _owner_codec("representation")),
        (
            "fixture_configuration_ref",
            _generator_ref_codec(BurgersFixtureConfigurationRef),
        ),
        (
            "corpus_owner_unavailable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "near_duplicate_policy_unavailable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
    ),
)

_register_canonical_type(
    ComparisonCorpusDecision,
    object_kind="comparison_corpus_decision",
    fields=(
        ("request", _nested(PostResultDuplicateRequest)),
        ("availability", _enum(ComparisonCorpusAvailability)),
        ("corpus_results", _tuple_of(_nested(RecordRefPair))),
        (
            "corpus_issuance_ref",
            _optional(_owner_codec("authority_evidence")),
        ),
        (
            "unavailable_reason_ref",
            _optional(_owner_codec("applicability_reason")),
        ),
    ),
)

_register_nested_canonical_type(
    DuplicateComparisonRequest,
    record_type="duplicate_comparison_request",
    fields=(
        ("subject_case_ref", _top_ref_codec(CanonicalChallengeCaseRef)),
        (
            "subject_physical_payload_fingerprint",
            _record(PhysicalPayloadFingerprint),
        ),
        (
            "subject_physical_payload_fingerprint_ref",
            _generator_ref_codec(PhysicalPayloadFingerprintRef),
        ),
        ("corpus_decision", _record(ComparisonCorpusDecision)),
        (
            "corpus_decision_ref",
            _generator_ref_codec(ComparisonCorpusDecisionRef),
        ),
        (
            "corpus_case_refs",
            _tuple_of(_top_ref_codec(CanonicalChallengeCaseRef)),
        ),
        (
            "corpus_physical_payload_fingerprints",
            _tuple_of(_record(PhysicalPayloadFingerprint)),
        ),
        (
            "corpus_physical_payload_fingerprint_refs",
            _tuple_of(_generator_ref_codec(PhysicalPayloadFingerprintRef)),
        ),
    ),
)

_register_nested_canonical_type(
    NearDuplicateRequest,
    record_type="near_duplicate_request",
    fields=(
        ("post_result_request", _nested(PostResultDuplicateRequest)),
        ("corpus_decision", _record(ComparisonCorpusDecision)),
        (
            "corpus_decision_ref",
            _generator_ref_codec(ComparisonCorpusDecisionRef),
        ),
        ("duplicate_rule_ref", _owner_codec("duplicate_rule")),
        (
            "semantic_equivalence_ref",
            _owner_codec("semantic_equivalence"),
        ),
        (
            "policy_unavailable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
    ),
)

_register_nested_canonical_type(
    NearDuplicateDecision,
    record_type="near_duplicate_decision",
    fields=(
        ("request", _nested(NearDuplicateRequest)),
        ("decision_kind", _enum(NearDuplicateDecisionKind)),
        (
            "semantic_equivalence_ref",
            _optional(_owner_codec("semantic_equivalence")),
        ),
        ("fact_ref", _optional(_owner_codec("evidence_artifact"))),
        ("audit_evidence_ref", _optional(_owner_codec("audit_evidence"))),
        ("duplicate_rule_ref", _optional(_owner_codec("duplicate_rule"))),
        (
            "unavailable_reason_ref",
            _optional(_owner_codec("applicability_reason")),
        ),
    ),
)

_register_canonical_type(
    DuplicateConformanceFacts,
    object_kind="duplicate_conformance_facts",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("post_result_request", _nested(PostResultDuplicateRequest)),
        ("corpus_decision", _record(ComparisonCorpusDecision)),
        (
            "corpus_decision_ref",
            _generator_ref_codec(ComparisonCorpusDecisionRef),
        ),
        (
            "duplicate_comparison_request_binding",
            _applicability_codec(_nested(DuplicateComparisonRequest)),
        ),
        (
            "canonical_case_duplicate_binding",
            _applicability_codec(_BOOL),
        ),
        (
            "physical_instance_collision_binding",
            _applicability_codec(_BOOL),
        ),
        (
            "near_duplicate_decision_binding",
            _applicability_codec(_nested(NearDuplicateDecision)),
        ),
    ),
)

_register_nested_canonical_type(
    ExternalDistributionFactRequest,
    record_type="external_distribution_fact_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("result_pairs", _tuple_of(_nested(RecordRefPair))),
        ("intended_unit_pairs", _tuple_of(_nested(RecordRefPair))),
        ("accounting_summary", _record(GenerationAccountingSummary)),
        (
            "accounting_summary_ref",
            _generator_ref_codec(GenerationAccountingSummaryRef),
        ),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        ("requested_fact_kind", _enum(ExternalDistributionFactKind)),
        (
            "statistics_objective_ref",
            _owner_codec("statistics_objective"),
        ),
        (
            "owner_unavailable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
    ),
)

_register_nested_canonical_type(
    ExternalFactAvailability,
    record_type="external_fact_availability",
    fields=(
        ("availability", _enum(ExternalFactAvailabilityKind)),
        ("fact_kind", _optional(_enum(ExternalDistributionFactKind))),
        (
            "statistics_objective_ref",
            _optional(_owner_codec("statistics_objective")),
        ),
        ("fact_ref", _optional(_owner_codec("evidence_artifact"))),
        ("audit_evidence_ref", _optional(_owner_codec("audit_evidence"))),
        (
            "unavailable_reason_ref",
            _optional(_owner_codec("applicability_reason")),
        ),
    ),
)

_register_nested_canonical_type(
    ExternalDistributionFactDecision,
    record_type="external_distribution_fact_decision",
    fields=(
        ("request", _nested(ExternalDistributionFactRequest)),
        ("availability", _nested(ExternalFactAvailability)),
    ),
)

_register_canonical_type(
    ExternalDistributionFactSet,
    object_kind="external_distribution_fact_set",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("result_pairs", _tuple_of(_nested(RecordRefPair))),
        ("intended_unit_pairs", _tuple_of(_nested(RecordRefPair))),
        ("accounting_summary", _record(GenerationAccountingSummary)),
        (
            "accounting_summary_ref",
            _generator_ref_codec(GenerationAccountingSummaryRef),
        ),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "decisions",
            _tuple_of(_nested(ExternalDistributionFactDecision)),
        ),
    ),
)


__all__ = (
    "CONFORMANCE_FALLBACK_SCHEMA",
    "SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID",
    "ComparisonCorpusAuthority",
    "ComparisonCorpusAvailability",
    "ComparisonCorpusDecision",
    "DeterministicReplayComparison",
    "DuplicateComparisonRequest",
    "DuplicateConformanceFacts",
    "ExternalDistributionFactAuthority",
    "ExternalDistributionFactDecision",
    "ExternalDistributionFactKind",
    "ExternalDistributionFactRequest",
    "ExternalDistributionFactSet",
    "ExternalFactAvailability",
    "ExternalFactAvailabilityKind",
    "FixtureReplayProbe",
    "FixtureReplayProbeRecord",
    "GeneratorConformanceFacts",
    "NearDuplicateDecision",
    "NearDuplicateDecisionKind",
    "NearDuplicatePolicyAuthority",
    "NearDuplicateRequest",
    "PostResultDuplicateRequest",
    "ReplayIdentityFacts",
    "build_duplicate_comparison_request",
    "build_duplicate_conformance_facts",
    "build_external_distribution_fact_request",
    "build_external_distribution_fact_set",
    "build_fixture_replay_probe",
    "build_generator_conformance_facts",
    "build_near_duplicate_request",
    "build_post_result_duplicate_request",
    "compare_fixture_replay",
    "decide_comparison_corpus",
    "decide_external_distribution_fact",
    "decide_near_duplicate",
)
