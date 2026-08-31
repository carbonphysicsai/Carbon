"""Trusted in-process B-03 fixture-generation composition.

This module is deliberately not a transport.  It admits one complete protected
request, consumes one fixture-only A4 grant, and composes the exact B-02A case,
authority, accounting, and conformance records.  It owns no population rule,
support predicate, censoring policy, replacement policy, threshold, reference
truth, measurement, qualification, retry loop, or LIVE decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import final

from carbon.authoring.cases import (
    CanonicalChallengeCase,
    CaseSourceBinding,
    CaseSourceKind,
    GeneratedCaseSource,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import (
    CanonicalCaseDisposition,
    CaseStatePayload,
    ExcludedCasePayload,
    GenerationFailurePayload,
    ReplacementDecision,
    ValidCasePayload,
)
from carbon.authoring.loading import (
    GraphOriginTag,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import (
    ApplicabilityBinding,
    ApplicabilityTag,
    CaseState,
    validate_loaded_authoring_graph,
)
from carbon.authoring.physical import validate_candidate_against_physical
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    owner_ref,
    require_owner_ref,
)
from carbon.authoring.sampling import (
    ReplacementTrigger,
    ReplacementTriggerKind,
)
from carbon.registry.model import ChallengeKey

from .accounting import (
    AttemptAccountingDecision,
    AttemptAccountingDirective,
    AttemptAccountingDirectiveKind,
    AttemptAccountingRequest,
    GenerationAttemptRecord,
    PendingGenerationAttempt,
    build_attempt_accounting_decision,
    build_generation_attempt_record,
    build_pending_generation_attempt,
    finalize_pending_accounting,
)
from .authorities import (
    CensoringDecision,
    CensoringVerdict,
    CensoringVerdictKind,
    FixtureGenerationAuthority,
    FixtureGenerationGrant,
    GeneratorCensoringRequest,
    IntendedUnitLinkDecision,
    IntendedUnitLinkRequest,
    PopulationAssessmentRole,
    PopulationSupportDecisionKind,
    SupportExclusionDecision,
    SupportExclusionDecisionKind,
    SupportExclusionRequest,
    finalize_censoring_decision,
)
from .burgers import (
    BurgersFixtureConfiguration,
    FixturePayloadFacts,
    GeneratedFixtureArtifact,
    PhysicalPayloadFingerprint,
    ProtectedBurgersFixturePayload,
    _materialize_burgers_fixture_payload,
    build_fixture_payload_facts,
    build_generated_fixture_artifact,
    build_physical_payload_fingerprint,
    build_validated_case_facts,
    burgers_fixture_configuration,
    burgers_fixture_configuration_ref,
)
from .canonical import canonical_content_digest
from .conformance import (
    CONFORMANCE_FALLBACK_SCHEMA,
    SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID,
    build_generator_conformance_facts,
)
from .errors import (
    GeneratorInputCode,
    GeneratorServiceCode,
    GeneratorServiceError,
    GeneratorValidationError,
)
from .model import (
    ApplicabilityReasonKind,
    FailureOccurrenceEvidenceCategory,
    GenerationSourceEvent,
    GeneratorFailureCatalogEntry,
    GeneratorFailureOccurrence,
    GeneratorFailureReason,
    GeneratorImplementationManifest,
    GeneratorInvocationOutput,
    GeneratorOutcomeKind,
    GeneratorRequest,
    GeneratorResult,
    GeneratorResultRecord,
    GeneratorTerminalStage,
    NamedApplicabilityReason,
    NamedConformanceFallback,
    RecordRefBinding,
    RecordRefPair,
    SourceMaterializationState,
    TerminalReasonCensoringDecision,
    TerminalReasonFailure,
    TerminalReasonNotApplicable,
    TerminalReasonSupportDecision,
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

_ACCOUNTING_REASON_ORDER = tuple(ApplicabilityReasonKind)[:7]
_RESULT_REASON_ORDER = tuple(ApplicabilityReasonKind)[7:]


def _wrong(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path=path)


def _stale(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.STALE_BINDING, path=path)


def _incomplete(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INCOMPLETE_BINDING, path=path)


def _authority_method(value: object, method_name: str, path: str):
    if type(value) is bool or value is None:
        raise GeneratorValidationError(
            GeneratorInputCode.AUTHORITY_INTERFACE_INVALID,
            path=path,
        )
    lookup_failed = False
    try:
        method = getattr(value, method_name, None)
    except Exception:  # noqa: BLE001 - hostile nominal-interface lookup
        lookup_failed = True
        method = None
    if lookup_failed:
        raise GeneratorValidationError(
            GeneratorInputCode.AUTHORITY_INTERFACE_INVALID,
            path=path,
        )
    if not callable(method):
        raise GeneratorValidationError(
            GeneratorInputCode.AUTHORITY_INTERFACE_INVALID,
            path=path,
        )
    return method


def _reason_ref(
    request: GeneratorRequest,
    kind: ApplicabilityReasonKind,
) -> object:
    for item in (
        *request.attempt_accounting_applicability_reasons,
        *request.result_applicability_reasons,
    ):
        if item.kind is kind:
            return item.reason_ref
    raise _incomplete("/applicability_reasons")


def _named_reason_tuple(
    value: object,
    expected: tuple[ApplicabilityReasonKind, ...],
    path: str,
) -> tuple[NamedApplicabilityReason, ...]:
    if type(value) is not tuple or len(value) != len(expected):
        raise _incomplete(path)
    if any(type(item) is not NamedApplicabilityReason for item in value):
        raise _wrong(path)
    if tuple(item.kind for item in value) != expected:
        raise _invalid(path)
    if len({item.reason_ref for item in value}) != len(value):
        raise _invalid(path)
    return value


def _validate_conformance_fallbacks(request: GeneratorRequest) -> None:
    values = request.conformance_fallbacks
    if (
        type(values) is not tuple
        or len(values) != len(CONFORMANCE_FALLBACK_SCHEMA)
        or any(type(item) is not NamedConformanceFallback for item in values)
        or tuple(item.fallback_id for item in values) != CONFORMANCE_FALLBACK_SCHEMA
    ):
        raise _invalid("/conformance_fallbacks")
    checked: list[object] = []
    for index, item in enumerate(values):
        expected_kind = (
            "infrastructure_failure"
            if item.fallback_id == SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID
            else "applicability_reason"
        )
        try:
            ref = require_owner_ref(item.fallback_ref, expected_kind)
        except (AuthoringError, TypeError, ValueError):
            ref = None
        if ref is None:
            raise _wrong(f"/conformance_fallbacks/{index}/fallback_ref")
        scope = ref.scope_binding
        if (
            type(scope) is not ChallengeScope
            or scope.challenge_key != request.challenge_key
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path=f"/conformance_fallbacks/{index}/fallback_ref",
            )
        checked.append(ref)
    if len(set(checked)) != len(checked):
        raise _invalid("/conformance_fallbacks")
    support_fallback = next(
        item.fallback_ref
        for item in values
        if item.fallback_id == SUPPORT_OWNER_UNAVAILABLE_FALLBACK_ID
    )
    catalog_fallback = _failure_entry(
        request,
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
    ).occurrence_evidence_fallback
    if support_fallback != catalog_fallback:
        raise _stale("/conformance_fallbacks")


def burgers_fixture_implementation_manifest(
    challenge_key: ChallengeKey,
) -> GeneratorImplementationManifest:
    """Return the sole semantic B-03 v1 implementation manifest."""

    if type(challenge_key) is not ChallengeKey:
        raise _wrong("/challenge_key")
    return GeneratorImplementationManifest(
        implementation_id="carbon_generators_burgers_fixture",
        implementation_version="1.0",
        package="carbon.generators.burgers",
        runtime_contract_version="0.1",
        canonical_profile="carbon_generator_runtime_canonical_v1",
        fixture_configuration_ref=burgers_fixture_configuration_ref(challenge_key),
        latent_codec_id="carbon.b03.burgers.fixture-latent.v1",
    )


def _validate_failure_catalog(request: GeneratorRequest) -> None:
    entries = request.failure_reason_catalog
    if type(entries) is not tuple or len(entries) != len(_FAILURE_CATALOG_SCHEMA):
        raise _incomplete("/failure_reason_catalog")
    for entry, expected in zip(entries, _FAILURE_CATALOG_SCHEMA, strict=True):
        if type(entry) is not GeneratorFailureCatalogEntry:
            raise _wrong("/failure_reason_catalog")
        reason = entry.reason
        outcome, stage, reason_id, reason_code, category = expected
        if (
            reason.challenge_key != request.challenge_key
            or reason.outcome_kind is not outcome
            or reason.terminal_stage is not stage
            or reason.reason_id != reason_id
            or reason.reason_version != "1.0"
            or reason.reason_code != reason_code
            or reason.occurrence_evidence_category is not category
            or reason.to_ref() != entry.reason_ref
        ):
            raise _stale("/failure_reason_catalog")
        generation_alias = entry.generation_failure_alias_binding
        replacement_alias = entry.replacement_eligible_generation_failure_alias_binding
        if outcome is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
            if not generation_alias.is_bound or not replacement_alias.is_bound:
                raise _incomplete("/failure_reason_catalog")
            generation_ref = require_owner_ref(
                generation_alias.value,
                "generation_failure",
            )
            replacement_ref = require_owner_ref(
                replacement_alias.value,
                "replacement_eligible_generation_failure_reason",
            )
            pins = (
                "scope_binding",
                "object_id",
                "object_version",
                "content_digest",
            )
            if any(
                getattr(generation_ref, name) != getattr(replacement_ref, name)
                for name in pins
            ) or (
                generation_ref.object_id != reason.reason_id
                or generation_ref.object_version != reason.reason_version
                or generation_ref.content_digest != canonical_content_digest(reason)
            ):
                raise _stale("/failure_reason_catalog")
        elif (
            generation_alias.is_bound
            or replacement_alias.is_bound
            or generation_alias.value != replacement_alias.value
        ):
            raise _invalid("/failure_reason_catalog")


def _failure_entry(
    request: GeneratorRequest,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
) -> GeneratorFailureCatalogEntry:
    matches = tuple(
        entry
        for entry in request.failure_reason_catalog
        if entry.reason.outcome_kind is outcome_kind
        and entry.reason.terminal_stage is terminal_stage
    )
    if len(matches) != 1:
        raise _incomplete("/failure_reason_catalog")
    return matches[0]


def _authoring_ref_key(value: object) -> tuple[object, ...]:
    """Mirror B-02A's canonical resolved/load ordering for exact refs."""

    key: tuple[object, ...] = (
        value.object_kind,
        value.challenge_key.challenge_id,
        value.challenge_key.version,
        value.object_id,
        value.object_version,
        value.schema_version,
        value.canonicalization_profile,
        value.content_digest,
    )
    if type(value) is InstanceDistributionContractRef:
        return (*key, value.expected_population_role)
    if type(value) is CanonicalChallengeCaseRef:
        return (*key, value.disclosure_class)
    return key


def _validate_loaded_bundle(request: GeneratorRequest) -> None:
    from carbon.authoring.model import validate_loaded_authoring_graph

    bundle = request.authoring_bundle
    resolved_refs = tuple(ref for ref, _ in bundle.resolved_dependencies)
    loaded_refs = tuple(item.expected_ref for item in bundle.loaded_dependencies)
    if not resolved_refs or resolved_refs != loaded_refs:
        raise _incomplete("/authoring_bundle/loaded_dependencies")
    objects = bundle.objects_by_ref()
    pending = [
        bundle.physical_system_ref,
        bundle.candidate_output_ref,
        bundle.primary_population_ref,
        bundle.selection_population_ref,
        bundle.sampling_plan_ref,
    ]
    reachable: set[object] = set()
    while pending:
        ref = pending.pop()
        if ref in reachable:
            continue
        authored_object = objects.get(ref)
        if authored_object is None:
            raise _incomplete("/authoring_bundle/resolved_dependencies")
        reachable.add(ref)
        try:
            dependencies = authored_object.dependency_refs()
        except (AttributeError, AuthoringError, TypeError, ValueError):
            dependencies = None
        if dependencies is None:
            raise _invalid("/authoring_bundle/resolved_dependencies")
        for dependency_ref in dependencies:
            if dependency_ref not in objects:
                raise _incomplete("/authoring_bundle/resolved_dependencies")
            pending.append(dependency_ref)
    canonical_refs = tuple(sorted(reachable, key=_authoring_ref_key))
    if resolved_refs != canonical_refs:
        raise _invalid("/authoring_bundle/resolved_dependencies")
    for (ref, authored_object), loaded in zip(
        bundle.resolved_dependencies,
        bundle.loaded_dependencies,
        strict=True,
    ):
        if (
            loaded.expected_ref != ref
            or loaded.recomputed_ref != ref
            or loaded.authored_object != authored_object
            or loaded.verified_bytes != authored_object.canonical_bytes()
        ):
            raise _stale("/authoring_bundle/loaded_dependencies")
    try:
        validate_loaded_authoring_graph(objects)
    except (AuthoringError, TypeError, ValueError):
        graph_valid = False
    else:
        graph_valid = True
    if not graph_valid:
        raise _invalid("/authoring_bundle")


def _validate_link_decision(request: GeneratorRequest) -> None:
    supplied = request.intended_unit_link_decision
    if type(supplied) is not IntendedUnitLinkDecision:
        raise _wrong("/intended_unit_link_decision")
    if type(supplied.request) is not IntendedUnitLinkRequest:
        raise _wrong("/intended_unit_link_decision/request")
    link = replace(supplied.request)
    decision = IntendedUnitLinkDecision(
        challenge_key=supplied.challenge_key,
        request=link,
        link_evidence_ref=supplied.link_evidence_ref,
    )
    if decision != supplied:
        raise _stale("/intended_unit_link_decision")
    if decision.to_ref() != request.intended_unit_link_decision_ref:
        raise _stale("/intended_unit_link_decision_ref")
    expected = (
        (link.challenge_key, request.challenge_key),
        (link.sampling_plan_ref, request.authoring_bundle.sampling_plan_ref),
        (
            link.selection_population_ref,
            request.authoring_bundle.selection_population_ref,
        ),
        (link.role_binding, request.role_binding),
        (link.replay_ref, request.replay_ref),
        (link.intended_slot_ref, request.intended_slot_ref),
        (
            link.intended_evidence_unit_ref,
            request.intended_evidence_unit_ref,
        ),
        (link.attempt_ref, request.attempt_ref),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise _stale("/intended_unit_link_decision")


def _validate_construction_binding(request: GeneratorRequest) -> None:
    bundle = request.authoring_bundle
    plan = bundle.sampling_plan
    binding = request.case_construction
    if (
        bundle.physical_system_ref != request.generator.supported_physical_system_ref
        or bundle.candidate_output_ref
        != request.generator.supported_candidate_output_ref
        or bundle.primary_population_ref
        != request.generator.supported_primary_population_ref
        or bundle.selection_population_ref
        != request.generator.supported_selection_population_ref
        or plan.to_ref() != bundle.sampling_plan_ref
        or plan.primary_population_ref != bundle.primary_population_ref
        or plan.selection_population_ref != bundle.selection_population_ref
        or plan.sampling_role is not request.role_binding.sampling_role
        or request.role_binding.sampling_plan_ref != bundle.sampling_plan_ref
    ):
        raise _stale("/authoring_bundle")
    if (
        binding.query_population_binding != plan.query_population_binding
        or binding.observation_population_binding != plan.observation_population_binding
        or binding.evidence_campaign_binding != plan.evidence_campaign_binding
        or not binding.intended_slot_binding.is_bound
        or binding.intended_slot_binding.value != request.intended_slot_ref
        or not binding.prospective_censoring_policy_binding.is_bound
        or binding.prospective_censoring_policy_binding.value
        != plan.censoring_policy_ref
        or not set(request.generator.source_provenance_refs).issubset(
            binding.case_provenance_refs
        )
    ):
        raise _stale("/case_construction")


def _validate_generator_request_content(
    request: object,
) -> tuple[GeneratorRequest, object, object]:
    """Reconstruct every immutable request commitment without authority access."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    identity = request.identity()
    request_ref = identity.to_ref()
    if request.challenge_key != request.authoring_bundle.challenge_key:
        raise _stale("/challenge_key")
    fixed_configuration = burgers_fixture_configuration()
    if (
        type(request.fixture_configuration) is not BurgersFixtureConfiguration
        or request.fixture_configuration is not fixed_configuration
        or request.fixture_configuration_ref
        != burgers_fixture_configuration_ref(request.challenge_key)
        or request.generator.fixture_configuration_ref
        != request.fixture_configuration_ref
        or request.generator.environment_ref != request.environment_ref
        or request.environment.challenge_key != request.challenge_key
    ):
        raise _stale("/fixture_configuration")
    manifest = burgers_fixture_implementation_manifest(request.challenge_key)
    if request.generator.implementation_digest != manifest.implementation_digest:
        raise _stale("/generator/implementation_digest")
    _named_reason_tuple(
        request.attempt_accounting_applicability_reasons,
        _ACCOUNTING_REASON_ORDER,
        "/attempt_accounting_applicability_reasons",
    )
    _named_reason_tuple(
        request.result_applicability_reasons,
        _RESULT_REASON_ORDER,
        "/result_applicability_reasons",
    )
    _validate_failure_catalog(request)
    _validate_conformance_fallbacks(request)
    if (
        len(
            {
                item.reason_ref
                for item in (
                    *request.attempt_accounting_applicability_reasons,
                    *request.result_applicability_reasons,
                )
            }
        )
        != 15
    ):
        raise _invalid("/result_applicability_reasons")
    _validate_loaded_bundle(request)
    _validate_link_decision(request)
    _validate_construction_binding(request)
    if request.replay_ref.challenge_key != request.challenge_key:
        raise GeneratorValidationError(
            GeneratorInputCode.CROSS_CHALLENGE,
            path="/replay_ref",
        )
    return request, identity, request_ref


def validate_generator_request(
    request: object,
    *,
    fixture_authority: object,
    support_authority: object,
    censoring_authority: object,
    accounting_authority: object,
) -> GeneratorRequest:
    """Run the complete no-provider admission boundary for one request."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    # Rebuild the complete public identity before consulting any injected
    # authority.  This rejects nested cross-Challenge refs and constructor-
    # bypassed identity values without consuming provider state.
    request.identity().to_ref()
    if type(fixture_authority) is not FixtureGenerationAuthority:
        raise GeneratorValidationError(
            GeneratorInputCode.AUTHORITY_INTERFACE_INVALID,
            path="/fixture_authority",
        )
    _authority_method(
        support_authority,
        "assess_support_exclusion",
        "/support_authority",
    )
    _authority_method(
        censoring_authority,
        "decide_censoring",
        "/censoring_authority",
    )
    _authority_method(
        accounting_authority,
        "decide_attempt_accounting",
        "/accounting_authority",
    )
    _validate_generator_request_content(request)
    fixture_authority.require_available(request.replay_ref)
    return request


def build_generation_source_event(
    request: GeneratorRequest,
    *,
    payload_ref: object | None,
    materialization_state: SourceMaterializationState,
) -> GenerationSourceEvent:
    """Build the acyclic protected source event exactly once per invocation."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    if type(materialization_state) is not SourceMaterializationState:
        raise _wrong("/materialization_state")
    if materialization_state is SourceMaterializationState.PAYLOAD_AVAILABLE:
        require_owner_ref(payload_ref, "protected_case_payload")
        payload_binding = ApplicabilityBinding.bound(payload_ref)
    else:
        if payload_ref is not None:
            raise _invalid("/payload_ref")
        payload_binding = ApplicabilityBinding.not_applicable(
            request.source_payload_inapplicable_reason_ref
        )
    return GenerationSourceEvent(
        challenge_key=request.challenge_key,
        request_ref=request.to_ref(),
        physical_system_ref=request.authoring_bundle.physical_system_ref,
        candidate_output_ref=request.authoring_bundle.candidate_output_ref,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        selection_population_ref=request.authoring_bundle.selection_population_ref,
        sampling_plan_ref=request.authoring_bundle.sampling_plan_ref,
        generator_ref=request.generator_ref,
        environment_ref=request.environment_ref,
        fixture_configuration_ref=request.fixture_configuration_ref,
        role_binding=request.role_binding,
        fixture_registration_ref=request.generator.fixture_registration_ref,
        source_provenance_refs=request.generator.source_provenance_refs,
        replay_ref=request.replay_ref,
        intended_slot_ref=request.intended_slot_ref,
        intended_evidence_unit_ref=request.intended_evidence_unit_ref,
        attempt_ref=request.attempt_ref,
        payload_ref_binding=payload_binding,
        materialization_state=materialization_state,
    )


@final
@dataclass(frozen=True, slots=True, repr=False)
class _MaterializedFixture:
    payload: ProtectedBurgersFixturePayload
    payload_ref: object
    fingerprint: PhysicalPayloadFingerprint
    payload_facts: FixturePayloadFacts
    source_event: GenerationSourceEvent

    def __repr__(self) -> str:
        return "_MaterializedFixture(<protected>)"


def _materialize_fixture(
    request: GeneratorRequest,
    grant: FixtureGenerationGrant,
) -> _MaterializedFixture:
    if type(grant) is not FixtureGenerationGrant or grant.request is not request:
        raise GeneratorServiceError(GeneratorServiceCode.INTERNAL_FAILURE)
    derived = grant.derive_once(request.role_binding)
    payload = _materialize_burgers_fixture_payload(
        derived,
        fixture_configuration_ref=request.fixture_configuration_ref,
    )
    del derived
    payload_ref = owner_ref(
        "protected_case_payload",
        scope_binding=ChallengeScope(request.challenge_key),
        object_id=request.attempt_ref.object_id,
        object_version=request.attempt_ref.object_version,
        content_digest=canonical_content_digest(payload),
    )
    fingerprint = build_physical_payload_fingerprint(
        challenge_key=request.challenge_key,
        case_representation_ref=request.case_construction.case_representation_ref,
        fixture_configuration_ref=request.fixture_configuration_ref,
        protected_payload=payload,
    )
    payload_facts = build_fixture_payload_facts(
        protected_payload=payload,
        protected_payload_ref=payload_ref,
        physical_payload_fingerprint=fingerprint,
        physical_payload_fingerprint_ref=fingerprint.to_ref(),
    )
    event = build_generation_source_event(
        request,
        payload_ref=payload_ref,
        materialization_state=SourceMaterializationState.PAYLOAD_AVAILABLE,
    )
    return _MaterializedFixture(
        payload,
        payload_ref,
        fingerprint,
        payload_facts,
        event,
    )


def build_support_exclusion_request(
    request: GeneratorRequest,
    materialized: _MaterializedFixture,
) -> SupportExclusionRequest:
    """Bind the exact pre-case support/exclusion authority request."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    if type(materialized) is not _MaterializedFixture:
        raise _wrong("/materialized")
    return SupportExclusionRequest(
        challenge_key=request.challenge_key,
        generator_request_ref=request.to_ref(),
        source_event=materialized.source_event,
        source_event_ref=materialized.source_event.to_ref(),
        protected_payload=materialized.payload,
        protected_payload_ref=materialized.payload_ref,
        physical_system_ref=request.authoring_bundle.physical_system_ref,
        candidate_output_ref=request.authoring_bundle.candidate_output_ref,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        selection_population_ref=request.authoring_bundle.selection_population_ref,
        sampling_plan_ref=request.authoring_bundle.sampling_plan_ref,
        generator_ref=request.generator_ref,
        environment_ref=request.environment_ref,
        fixture_configuration_ref=request.fixture_configuration_ref,
        role_binding=request.role_binding,
        replay_ref=request.replay_ref,
        intended_slot_ref=request.intended_slot_ref,
        intended_evidence_unit_ref=request.intended_evidence_unit_ref,
        attempt_ref=request.attempt_ref,
        fixture_payload_facts=materialized.payload_facts,
    )


def _validate_support_decision_echo(
    request: GeneratorRequest,
    decision: SupportExclusionDecision,
) -> None:
    """Require every authority-selected support value to echo admitted authority."""

    fallback = _failure_entry(
        request,
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
    ).occurrence_evidence_fallback
    if decision.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE:
        if decision.infrastructure_failure_ref != fallback:
            raise _stale("/support_decision/infrastructure_failure_ref")
        return

    populations = (
        request.authoring_bundle.selection_population,
        request.authoring_bundle.primary_population,
    )
    for assessment, population in zip(
        decision.assessments,
        populations,
        strict=True,
    ):
        # Re-run the exact assessment constructor so a nominally exact object
        # created by bypassing dataclass initialization cannot smuggle scoped
        # evidence across a Challenge boundary.
        assessment = replace(assessment)
        if assessment.support_contract != population.support_contract:
            raise _stale("/support_decision/assessments/support_contract")
        if (
            assessment.decision_kind
            is PopulationSupportDecisionKind.REGISTERED_EXCLUSION
        ):
            exclusion = assessment.exclusion_contract_binding
            if not exclusion.is_bound or exclusion.value not in population.exclusions:
                raise _stale("/support_decision/assessments/exclusion_contract_binding")
        if (
            assessment.decision_kind
            is PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE
        ):
            infrastructure = assessment.infrastructure_failure_binding
            if not infrastructure.is_bound or infrastructure.value != fallback:
                raise _stale(
                    "/support_decision/assessments/infrastructure_failure_binding"
                )


def assess_support_exclusion(
    request: GeneratorRequest,
    materialized: _MaterializedFixture,
    support_authority: object,
) -> SupportExclusionDecision:
    """Call one nominal owner once and fail closed to its admitted fallback."""

    support_request = build_support_exclusion_request(request, materialized)
    try:
        method = _authority_method(
            support_authority,
            "assess_support_exclusion",
            "/support_authority",
        )
        decision = method(support_request)
        if type(decision) is not SupportExclusionDecision:
            raise _wrong("/support_decision")
        decision = replace(decision)
        if decision.request != support_request:
            raise _stale("/support_decision/request")
        _validate_support_decision_echo(request, decision)
        # Recompute now so a semantically incomplete echo cannot survive until
        # result construction.
        decision.to_ref()
        return decision
    except Exception:  # noqa: BLE001 - external support-authority boundary
        fallback = _failure_entry(
            request,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
            GeneratorTerminalStage.SUPPORT_AUTHORITY,
        ).occurrence_evidence_fallback
        return SupportExclusionDecision(
            challenge_key=request.challenge_key,
            request=support_request,
            decision_kind=SupportExclusionDecisionKind.OWNER_UNAVAILABLE,
            assessments=(),
            terminal_resolution=(PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE),
            effective_assessment_role=None,
            resolution_policy_ref=None,
            resolution_evidence_ref=None,
            infrastructure_failure_ref=fallback,
        )


def support_terminal_classification(
    decision: SupportExclusionDecision,
) -> tuple[GeneratorOutcomeKind, GeneratorTerminalStage] | None:
    """Map only the externally selected terminal support resolution."""

    if type(decision) is not SupportExclusionDecision:
        raise _wrong("/support_decision")
    resolution = decision.terminal_resolution
    if resolution is PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT:
        return None
    outcome = {
        PopulationSupportDecisionKind.REGISTERED_EXCLUSION: (
            GeneratorOutcomeKind.REGISTERED_EXCLUSION
        ),
        PopulationSupportDecisionKind.OUTSIDE_REGISTERED_SUPPORT: (
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE
        ),
        PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE: (
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        ),
    }[resolution]
    return outcome, GeneratorTerminalStage.SUPPORT_AUTHORITY


def build_generated_case(
    request: GeneratorRequest,
    *,
    source_event: GenerationSourceEvent,
    payload_ref: object,
) -> CanonicalChallengeCase:
    """Construct the sole B-02A case shape owned by the B-03 fixture."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    if type(source_event) is not GenerationSourceEvent:
        raise _wrong("/source_event")
    if (
        source_event.request_ref != request.to_ref()
        or source_event.payload_ref_binding.tag is not ApplicabilityTag.BOUND
        or source_event.payload_ref_binding.value != payload_ref
    ):
        raise _stale("/source_event")
    binding = request.case_construction
    return CanonicalChallengeCase(
        object_kind="canonical_challenge_case",
        schema_version=AUTHORING_SCHEMA_VERSION,
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=request.challenge_key,
        object_id=binding.object_id,
        object_version=binding.object_version,
        supersedes=binding.supersedes,
        physical_system_ref=request.authoring_bundle.physical_system_ref,
        candidate_output_ref=request.authoring_bundle.candidate_output_ref,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        related_population_bindings=binding.related_population_bindings,
        sampling_plan_binding=ApplicabilityBinding.bound(
            request.authoring_bundle.sampling_plan_ref
        ),
        case_source=CaseSourceBinding(
            CaseSourceKind.GENERATED,
            GeneratedCaseSource(source_event.to_ref(), request.generator_ref),
        ),
        case_representation_ref=binding.case_representation_ref,
        physical_payload_ref=payload_ref,
        query_population_binding=binding.query_population_binding,
        observation_population_binding=binding.observation_population_binding,
        evidence_campaign_binding=binding.evidence_campaign_binding,
        intended_slot_binding=binding.intended_slot_binding,
        prospective_censoring_policy_binding=(
            binding.prospective_censoring_policy_binding
        ),
        applicability_bindings=binding.applicability_bindings,
        disclosure_class=binding.disclosure_class,
        disclosure_contract=binding.disclosure_contract,
        case_provenance_refs=binding.case_provenance_refs,
    )


def build_generated_artifact(
    request: GeneratorRequest,
    *,
    grant: FixtureGenerationGrant,
    case: CanonicalChallengeCase,
) -> GeneratedFixtureArtifact:
    """Load and graph-validate one generated case with fixture provenance."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    if type(grant) is not FixtureGenerationGrant or grant.request is not request:
        raise _wrong("/grant")
    if type(case) is not CanonicalChallengeCase:
        raise _wrong("/case")
    case_ref = case.to_ref()
    dependency_refs = tuple(
        item.expected_ref for item in request.authoring_bundle.loaded_dependencies
    )
    if not set(case.dependency_refs()).issubset(dependency_refs):
        raise _incomplete("/authoring_bundle/loaded_dependencies")
    loaded_case = load_authoring_bytes(
        case_ref,
        case.canonical_bytes(),
        origin=grant.origin,
        origin_evidence_ref=request.fixture_loading.origin_evidence_ref,
        source_provenance_refs=request.generator.source_provenance_refs,
        audit_evidence_refs=request.fixture_loading.audit_evidence_refs,
        qualification_evidence=request.fixture_loading.qualification_evidence,
    )
    graph_origin = compose_authoring_graph_origin(
        root=loaded_case,
        dependencies=request.authoring_bundle.loaded_dependencies,
        expected_dependency_refs=dependency_refs,
        composition_audit_ref=request.fixture_loading.composition_audit_ref,
        registered_authority=None,
    )
    if graph_origin.graph_origin is not GraphOriginTag.FIXTURE_DERIVED:
        raise _invalid("/graph_origin")
    objects = request.authoring_bundle.objects_by_ref()
    objects[case_ref] = case
    from carbon.authoring.model import validate_loaded_authoring_graph

    validate_loaded_authoring_graph(objects)
    return build_generated_fixture_artifact(
        case=case,
        case_ref=case_ref,
        loaded_case=loaded_case,
        loaded_dependencies=request.authoring_bundle.loaded_dependencies,
        graph_origin=graph_origin,
    )


def failure_occurrence(
    request: GeneratorRequest,
    source_event: GenerationSourceEvent,
    *,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
) -> tuple[
    GeneratorFailureReason,
    object,
    GeneratorFailureOccurrence,
    object,
]:
    """Select the sole admitted stable reason and build its non-echo occurrence."""

    if type(request) is not GeneratorRequest:
        raise _wrong("/request")
    if type(source_event) is not GenerationSourceEvent:
        raise _wrong("/source_event")
    matches = tuple(
        entry
        for entry in request.failure_reason_catalog
        if entry.reason.outcome_kind is outcome_kind
        and entry.reason.terminal_stage is terminal_stage
    )
    if len(matches) != 1:
        raise _incomplete("/failure_reason_catalog")
    entry = matches[0]
    occurrence = GeneratorFailureOccurrence(
        challenge_key=request.challenge_key,
        request_ref=request.to_ref(),
        source_event_ref=source_event.to_ref(),
        reason=entry.reason,
        reason_ref=entry.reason_ref,
        generation_failure_alias_binding=(entry.generation_failure_alias_binding),
        replacement_eligible_generation_failure_alias_binding=(
            entry.replacement_eligible_generation_failure_alias_binding
        ),
        outcome_kind=outcome_kind,
        terminal_stage=terminal_stage,
        occurrence_evidence_binding=ApplicabilityBinding.bound(
            entry.occurrence_evidence_fallback
        ),
    )
    return entry.reason, entry.reason_ref, occurrence, occurrence.to_ref()


def _failure_bindings(
    request: GeneratorRequest,
    source_event: GenerationSourceEvent,
    *,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
) -> tuple[RecordRefBinding, RecordRefBinding]:
    reason, reason_ref, occurrence, occurrence_ref = failure_occurrence(
        request,
        source_event,
        outcome_kind=outcome_kind,
        terminal_stage=terminal_stage,
    )
    return (
        RecordRefBinding.bound(reason, reason_ref),
        RecordRefBinding.bound(occurrence, occurrence_ref),
    )


def _not_applicable_binding(
    request: GeneratorRequest,
    kind: ApplicabilityReasonKind,
) -> RecordRefBinding:
    return RecordRefBinding.not_applicable(_reason_ref(request, kind))


@final
@dataclass(frozen=True, slots=True, repr=False)
class _TerminalMaterial:
    """Internal reached-milestone bundle; never canonical or externally exposed."""

    source_event: GenerationSourceEvent
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    applicability_stage: GeneratorTerminalStage
    payload_facts: FixturePayloadFacts | None
    support_decision: SupportExclusionDecision | None
    artifact: GeneratedFixtureArtifact | None
    censoring_request: GeneratorCensoringRequest | None
    censoring_verdict: CensoringVerdict | None
    failure_reason_binding: RecordRefBinding
    failure_occurrence_binding: RecordRefBinding

    def __repr__(self) -> str:
        return "_TerminalMaterial(<protected>)"


def _owner_alias(
    kind: str,
    request: GeneratorRequest,
    *,
    content_digest: str,
) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(request.challenge_key),
        object_id=request.attempt_ref.object_id,
        object_version=request.attempt_ref.object_version,
        content_digest=content_digest,
    )


def _record_pair_binding(record: object, ref: object) -> RecordRefBinding:
    return RecordRefBinding.bound(record, ref)


def _support_binding(
    request: GeneratorRequest,
    decision: SupportExclusionDecision | None,
) -> RecordRefBinding:
    if decision is None:
        return _not_applicable_binding(
            request,
            ApplicabilityReasonKind.SUPPORT_DECISION_INAPPLICABLE,
        )
    return _record_pair_binding(decision, decision.to_ref())


def _artifact_binding(
    request: GeneratorRequest,
    artifact: GeneratedFixtureArtifact | None,
) -> RecordRefBinding:
    if artifact is None:
        return _not_applicable_binding(
            request,
            ApplicabilityReasonKind.CONSTRUCTED_CASE_INAPPLICABLE,
        )
    return _record_pair_binding(artifact.case, artifact.case_ref)


def _censoring_verdict_binding(
    request: GeneratorRequest,
    verdict: CensoringVerdict | None,
) -> RecordRefBinding:
    if verdict is None:
        return _not_applicable_binding(
            request,
            ApplicabilityReasonKind.CENSORING_VERDICT_INAPPLICABLE,
        )
    return _record_pair_binding(verdict, verdict.to_ref())


def _failure_na_bindings(
    request: GeneratorRequest,
) -> tuple[RecordRefBinding, RecordRefBinding]:
    reason_ref = _reason_ref(
        request,
        ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
    )
    return (
        RecordRefBinding.not_applicable(reason_ref),
        RecordRefBinding.not_applicable(reason_ref),
    )


def _terminal_material(
    request: GeneratorRequest,
    source_event: GenerationSourceEvent,
    *,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
    applicability_stage: GeneratorTerminalStage | None = None,
    payload_facts: FixturePayloadFacts | None = None,
    support_decision: SupportExclusionDecision | None = None,
    artifact: GeneratedFixtureArtifact | None = None,
    censoring_request: GeneratorCensoringRequest | None = None,
    censoring_verdict: CensoringVerdict | None = None,
) -> _TerminalMaterial:
    if outcome_kind in {
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
    }:
        failure_reason, failure_occurrence = _failure_bindings(
            request,
            source_event,
            outcome_kind=outcome_kind,
            terminal_stage=terminal_stage,
        )
    else:
        failure_reason, failure_occurrence = _failure_na_bindings(request)
    return _TerminalMaterial(
        source_event=source_event,
        outcome_kind=outcome_kind,
        terminal_stage=terminal_stage,
        applicability_stage=applicability_stage or terminal_stage,
        payload_facts=payload_facts,
        support_decision=support_decision,
        artifact=artifact,
        censoring_request=censoring_request,
        censoring_verdict=censoring_verdict,
        failure_reason_binding=failure_reason,
        failure_occurrence_binding=failure_occurrence,
    )


def _conformance_for(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> tuple[object, object]:
    validated_facts = (
        None
        if material.artifact is None
        else build_validated_case_facts(material.artifact)
    )
    support_ref = (
        None
        if material.support_decision is None
        else material.support_decision.to_ref()
    )
    return build_generator_conformance_facts(
        request=request,
        source_event=material.source_event,
        source_event_ref=material.source_event.to_ref(),
        outcome_kind=material.outcome_kind,
        terminal_stage=material.terminal_stage,
        applicability_stage=material.applicability_stage,
        payload_facts=material.payload_facts,
        support_decision=material.support_decision,
        support_decision_ref=support_ref,
        validated_case_facts=validated_facts,
    )


def _replacement_trigger_binding(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> ApplicabilityBinding[ReplacementTrigger]:
    if material.outcome_kind is GeneratorOutcomeKind.CENSORED_CASE:
        verdict = material.censoring_verdict
        if (
            type(verdict) is not CensoringVerdict
            or verdict.verdict_kind is not CensoringVerdictKind.CENSORED
            or verdict.basis is None
        ):
            raise _incomplete("/censoring_verdict")
        trigger = ReplacementTrigger(
            ReplacementTriggerKind.CENSORED,
            verdict.basis.censoring_reason,
        )
        return ApplicabilityBinding.bound(trigger)
    if material.outcome_kind is GeneratorOutcomeKind.REGISTERED_EXCLUSION:
        decision = material.support_decision
        if type(decision) is not SupportExclusionDecision:
            raise _incomplete("/support_decision")
        assessment = next(
            (
                item
                for item in decision.assessments
                if item.assessment_role is decision.effective_assessment_role
            ),
            None,
        )
        if (
            assessment is None
            or not assessment.prospective_exclusion_contract_ref_binding.is_bound
        ):
            raise _incomplete("/support_decision/assessments")
        return ApplicabilityBinding.bound(
            ReplacementTrigger(
                ReplacementTriggerKind.EXCLUDED,
                assessment.prospective_exclusion_contract_ref_binding.value,
            )
        )
    if material.outcome_kind is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
        occurrence_pair = material.failure_occurrence_binding.pair
        if occurrence_pair is None:
            raise _incomplete("/failure_occurrence_binding")
        alias = (
            occurrence_pair.record.replacement_eligible_generation_failure_alias_binding
        )
        if not alias.is_bound:
            raise _incomplete("/failure_occurrence_binding")
        return ApplicabilityBinding.bound(
            ReplacementTrigger(
                ReplacementTriggerKind.GENERATION_FAILURE,
                alias.value,
            )
        )
    return ApplicabilityBinding.not_applicable(
        _reason_ref(
            request,
            ApplicabilityReasonKind.REPLACEMENT_TRIGGER_INAPPLICABLE,
        )
    )


def build_attempt_accounting_request(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> AttemptAccountingRequest:
    """Build the exact post-outcome request without a final censoring record."""

    return AttemptAccountingRequest(
        challenge_key=request.challenge_key,
        request_identity=request.identity(),
        request_ref=request.to_ref(),
        source_event=material.source_event,
        source_event_ref=material.source_event.to_ref(),
        provisional_outcome=material.outcome_kind,
        provisional_stage=material.terminal_stage,
        support_decision_binding=_support_binding(
            request,
            material.support_decision,
        ),
        constructed_case_binding=_artifact_binding(request, material.artifact),
        censoring_verdict_binding=_censoring_verdict_binding(
            request,
            material.censoring_verdict,
        ),
        failure_reason_binding=material.failure_reason_binding,
        failure_occurrence_binding=material.failure_occurrence_binding,
        replacement_policy=request.authoring_bundle.sampling_plan.replacement_policy,
        replacement_trigger_binding=_replacement_trigger_binding(
            request,
            material,
        ),
        outcome_replacement_inapplicable_reason_ref=_reason_ref(
            request,
            ApplicabilityReasonKind.OUTCOME_REPLACEMENT_INAPPLICABLE,
        ),
        successor_authorization_inapplicable_reason_ref=_reason_ref(
            request,
            ApplicabilityReasonKind.SUCCESSOR_AUTHORIZATION_INAPPLICABLE,
        ),
        successor_execution_inapplicable_reason_ref=_reason_ref(
            request,
            ApplicabilityReasonKind.SUCCESSOR_EXECUTION_INAPPLICABLE,
        ),
        denominator_effect_inapplicable_reason_ref=_reason_ref(
            request,
            ApplicabilityReasonKind.DENOMINATOR_EFFECT_INAPPLICABLE,
        ),
        denominator_owner_unavailable_reason_ref=(
            request.attempt_accounting_fallback.denominator_unavailable_reason_ref
        ),
        accounting_authority_failure_ref=(
            request.attempt_accounting_fallback.authority_failure_ref
        ),
    )


def _accounting_owner_unavailable(
    request: AttemptAccountingRequest,
) -> AttemptAccountingDirective:
    return AttemptAccountingDirective(
        challenge_key=request.challenge_key,
        request=request,
        directive_kind=AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE,
        provisional_outcome=request.provisional_outcome,
        provisional_stage=request.provisional_stage,
        final_outcome=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        final_stage=GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
        outcome_replacement_binding=ApplicabilityBinding.not_applicable(
            request.outcome_replacement_inapplicable_reason_ref
        ),
        successor_authorization_binding=ApplicabilityBinding.not_applicable(
            request.successor_authorization_inapplicable_reason_ref
        ),
        denominator_effect_binding=ApplicabilityBinding.not_applicable(
            request.denominator_owner_unavailable_reason_ref
        ),
        accounting_authority_failure_ref=request.accounting_authority_failure_ref,
    )


def decide_attempt_accounting(
    request: AttemptAccountingRequest,
    accounting_authority: object,
) -> tuple[AttemptAccountingDirective, object]:
    """Call the admitted accounting owner once, then deterministically fail closed."""

    try:
        method = _authority_method(
            accounting_authority,
            "decide_attempt_accounting",
            "/accounting_authority",
        )
        directive = method(request)
        if type(directive) is not AttemptAccountingDirective:
            raise _wrong("/accounting_directive")
        directive = replace(directive)
        if directive.request != request:
            raise _stale("/accounting_directive/request")
        directive_ref = directive.to_ref()
        return directive, directive_ref
    except Exception:  # noqa: BLE001 - external nominal authority boundary
        directive = _accounting_owner_unavailable(request)
        return directive, directive.to_ref()


def build_censoring_request(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> GeneratorCensoringRequest:
    """Bind one validated fixture case to the prospective plan policy."""

    artifact = material.artifact
    if type(artifact) is not GeneratedFixtureArtifact:
        raise _incomplete("/artifact")
    policy_binding = artifact.case.prospective_censoring_policy_binding
    if not policy_binding.is_bound:
        raise _incomplete("/prospective_censoring_policy_binding")
    plan = request.authoring_bundle.sampling_plan
    return GeneratorCensoringRequest(
        challenge_key=request.challenge_key,
        case=artifact.case,
        case_ref=artifact.case_ref,
        source_event=material.source_event,
        source_event_ref=material.source_event.to_ref(),
        sampling_plan=plan,
        sampling_plan_ref=request.authoring_bundle.sampling_plan_ref,
        prospective_censoring_policy_ref=policy_binding.value,
        intended_evidence_unit_ref=request.intended_evidence_unit_ref,
        evidence_scope=request.disposition_construction.evidence_scope,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        selection_population_ref=(request.authoring_bundle.selection_population_ref),
        generator_ref=request.generator_ref,
        role_binding=request.role_binding,
    )


def decide_censoring(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    censoring_authority: object,
) -> tuple[GeneratorCensoringRequest, CensoringVerdict]:
    """Call one nominal censoring owner once and use the admitted fallback."""

    censoring_request = build_censoring_request(request, material)
    try:
        method = _authority_method(
            censoring_authority,
            "decide_censoring",
            "/censoring_authority",
        )
        verdict = method(censoring_request)
        if type(verdict) is not CensoringVerdict:
            raise _wrong("/censoring_verdict")
        verdict = replace(verdict)
        if verdict.request != censoring_request:
            raise _stale("/censoring_verdict/request")
        if verdict.verdict_kind is CensoringVerdictKind.AUTHORITY_UNAVAILABLE:
            expected_failure = _failure_entry(
                request,
                GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                GeneratorTerminalStage.CENSORING_AUTHORITY,
            ).occurrence_evidence_fallback
            if verdict.infrastructure_failure_ref != expected_failure:
                raise _stale("/censoring_verdict/infrastructure_failure_ref")
        verdict.to_ref()
        return censoring_request, verdict
    except Exception:  # noqa: BLE001 - external nominal authority boundary
        fallback = _failure_entry(
            request,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
            GeneratorTerminalStage.CENSORING_AUTHORITY,
        ).occurrence_evidence_fallback
        verdict = CensoringVerdict(
            challenge_key=request.challenge_key,
            request=censoring_request,
            verdict_kind=CensoringVerdictKind.AUTHORITY_UNAVAILABLE,
            basis=None,
            infrastructure_failure_ref=fallback,
        )
        return censoring_request, verdict


def _materialized_from_payload(
    request: GeneratorRequest,
    payload: ProtectedBurgersFixturePayload,
) -> _MaterializedFixture:
    payload_ref = owner_ref(
        "protected_case_payload",
        scope_binding=ChallengeScope(request.challenge_key),
        object_id=request.attempt_ref.object_id,
        object_version=request.attempt_ref.object_version,
        content_digest=canonical_content_digest(payload),
    )
    fingerprint = build_physical_payload_fingerprint(
        challenge_key=request.challenge_key,
        case_representation_ref=request.case_construction.case_representation_ref,
        fixture_configuration_ref=request.fixture_configuration_ref,
        protected_payload=payload,
    )
    payload_facts = build_fixture_payload_facts(
        protected_payload=payload,
        protected_payload_ref=payload_ref,
        physical_payload_fingerprint=fingerprint,
        physical_payload_fingerprint_ref=fingerprint.to_ref(),
    )
    event = build_generation_source_event(
        request,
        payload_ref=payload_ref,
        materialization_state=SourceMaterializationState.PAYLOAD_AVAILABLE,
    )
    return _MaterializedFixture(
        payload,
        payload_ref,
        fingerprint,
        payload_facts,
        event,
    )


def _no_payload_material(
    request: GeneratorRequest,
    *,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
    not_attempted: bool = False,
) -> _TerminalMaterial:
    event = build_generation_source_event(
        request,
        payload_ref=None,
        materialization_state=(
            SourceMaterializationState.NOT_ATTEMPTED
            if not_attempted
            else SourceMaterializationState.NO_PAYLOAD
        ),
    )
    return _terminal_material(
        request,
        event,
        outcome_kind=outcome_kind,
        terminal_stage=terminal_stage,
    )


def _support_terminal_material(
    request: GeneratorRequest,
    materialized: _MaterializedFixture,
    decision: SupportExclusionDecision,
) -> _TerminalMaterial | None:
    terminal = support_terminal_classification(decision)
    if terminal is None:
        return None
    outcome, stage = terminal
    return _terminal_material(
        request,
        materialized.source_event,
        outcome_kind=outcome,
        terminal_stage=stage,
        payload_facts=materialized.payload_facts,
        support_decision=decision,
    )


def _validated_terminal_material(
    request: GeneratorRequest,
    materialized: _MaterializedFixture,
    support_decision: SupportExclusionDecision,
    artifact: GeneratedFixtureArtifact,
    censoring_authority: object,
) -> _TerminalMaterial:
    reached = _terminal_material(
        request,
        materialized.source_event,
        outcome_kind=GeneratorOutcomeKind.VALID_GENERATED,
        terminal_stage=GeneratorTerminalStage.CENSORING_COMPLETION,
        payload_facts=materialized.payload_facts,
        support_decision=support_decision,
        artifact=artifact,
    )
    censoring_request, verdict = decide_censoring(
        request,
        reached,
        censoring_authority,
    )
    if verdict.verdict_kind is CensoringVerdictKind.NOT_CENSORED:
        outcome = GeneratorOutcomeKind.VALID_GENERATED
        stage = GeneratorTerminalStage.CENSORING_COMPLETION
    elif verdict.verdict_kind is CensoringVerdictKind.CENSORED:
        outcome = GeneratorOutcomeKind.CENSORED_CASE
        stage = GeneratorTerminalStage.CENSORING_COMPLETION
    else:
        outcome = GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        stage = GeneratorTerminalStage.CENSORING_AUTHORITY
    return _terminal_material(
        request,
        materialized.source_event,
        outcome_kind=outcome,
        terminal_stage=stage,
        payload_facts=materialized.payload_facts,
        support_decision=support_decision,
        artifact=artifact,
        censoring_request=censoring_request,
        censoring_verdict=verdict,
    )


def _primary_support_assessment(
    decision: SupportExclusionDecision,
) -> object:
    return next(
        (
            item
            for item in decision.assessments
            if item.assessment_role is PopulationAssessmentRole.PRIMARY_CASE
        ),
        None,
    )


def _effective_support_assessment(
    decision: SupportExclusionDecision,
) -> object:
    return next(
        (
            item
            for item in decision.assessments
            if item.assessment_role is decision.effective_assessment_role
        ),
        None,
    )


def _bound_applicability_value(binding: ApplicabilityBinding, path: str) -> object:
    if type(binding) is not ApplicabilityBinding or not binding.is_bound:
        raise _incomplete(path)
    return binding.value


def _case_state_payload(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    *,
    censoring_decision: CensoringDecision | None,
    attempt_record_ref: object,
    conformance_ref: object,
) -> CaseStatePayload:
    if material.outcome_kind is GeneratorOutcomeKind.VALID_GENERATED:
        decision = material.support_decision
        if type(decision) is not SupportExclusionDecision:
            raise _incomplete("/support_decision")
        assessment = _primary_support_assessment(decision)
        if assessment is None:
            raise _incomplete("/support_decision/assessments")
        payload = ValidCasePayload(
            applicability_evidence_ref=_bound_applicability_value(
                assessment.applicability_evidence_binding,
                "/support_decision/primary/applicability_evidence_binding",
            ),
            membership_evidence_ref=_bound_applicability_value(
                assessment.membership_evidence_binding,
                "/support_decision/primary/membership_evidence_binding",
            ),
        )
        return CaseStatePayload(CaseState.VALID, payload)
    if material.outcome_kind is GeneratorOutcomeKind.CENSORED_CASE:
        if (
            type(censoring_decision) is not CensoringDecision
            or censoring_decision.censoring_record_ref is None
        ):
            raise _incomplete("/censoring_decision")
        return CaseStatePayload(
            CaseState.CENSORED,
            censoring_decision.censoring_record_ref,
        )
    if material.outcome_kind is GeneratorOutcomeKind.REGISTERED_EXCLUSION:
        decision = material.support_decision
        if type(decision) is not SupportExclusionDecision:
            raise _incomplete("/support_decision")
        assessment = _effective_support_assessment(decision)
        if assessment is None:
            raise _incomplete("/support_decision/assessments")
        payload = ExcludedCasePayload(
            exclusion_contract_ref=_bound_applicability_value(
                assessment.exclusion_contract_ref_binding,
                "/support_decision/exclusion_contract_ref_binding",
            ),
            assessment_ref=_bound_applicability_value(
                assessment.exclusion_assessment_ref_binding,
                "/support_decision/exclusion_assessment_ref_binding",
            ),
            prospective_screening_design_ref=_bound_applicability_value(
                assessment.screening_design_ref_binding,
                "/support_decision/screening_design_ref_binding",
            ),
            inclusion_probability_accounting_ref=_bound_applicability_value(
                assessment.inclusion_probability_accounting_ref_binding,
                "/support_decision/inclusion_probability_accounting_ref_binding",
            ),
        )
        return CaseStatePayload(CaseState.EXCLUDED, payload)
    if material.outcome_kind is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
        occurrence_pair = material.failure_occurrence_binding.pair
        if occurrence_pair is None:
            raise _incomplete("/failure_occurrence_binding")
        occurrence = occurrence_pair.record
        generation_alias = occurrence.generation_failure_alias_binding
        if not generation_alias.is_bound:
            raise _incomplete("/failure_occurrence_binding")
        source_ref = material.source_event.to_ref()
        payload = GenerationFailurePayload(
            source_ref=_owner_alias(
                "case_source",
                request,
                content_digest=source_ref.content_digest,
            ),
            failure_evidence_ref=generation_alias.value,
            distribution_conformance_ref=_owner_alias(
                "distribution_conformance",
                request,
                content_digest=conformance_ref.content_digest,
            ),
            accounting_ref=_owner_alias(
                "generation_failure_accounting",
                request,
                content_digest=attempt_record_ref.content_digest,
            ),
        )
        return CaseStatePayload(CaseState.GENERATION_FAILURE, payload)
    raise _invalid("/outcome_kind")


def _disposition_binding(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    *,
    accounting_decision: AttemptAccountingDecision,
    attempt_record_ref: object,
    conformance_ref: object,
    censoring_decision: CensoringDecision | None,
) -> RecordRefBinding:
    if material.outcome_kind not in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.REGISTERED_EXCLUSION,
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorOutcomeKind.CENSORED_CASE,
    }:
        return _not_applicable_binding(
            request,
            ApplicabilityReasonKind.DISPOSITION_INAPPLICABLE,
        )
    replacement = accounting_decision.outcome_replacement_binding
    if not replacement.is_bound or type(replacement.value) is not ReplacementDecision:
        raise _incomplete("/accounting_decision/outcome_replacement_binding")
    case_bearing = material.outcome_kind in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.CENSORED_CASE,
    }
    if case_bearing:
        if material.artifact is None:
            raise _incomplete("/artifact")
        case_ref_binding = ApplicabilityBinding.bound(material.artifact.case_ref)
        attempt_binding = ApplicabilityBinding.not_applicable(
            request.disposition_construction.attempt_inapplicable_reason_ref
        )
    else:
        case_ref_binding = ApplicabilityBinding.not_applicable(
            request.disposition_construction.case_inapplicable_reason_ref
        )
        attempt_binding = ApplicabilityBinding.bound(request.attempt_ref)
    state_payload = _case_state_payload(
        request,
        material,
        censoring_decision=censoring_decision,
        attempt_record_ref=attempt_record_ref,
        conformance_ref=conformance_ref,
    )
    construction = request.disposition_construction
    disposition = CanonicalCaseDisposition(
        schema_version=AUTHORING_SCHEMA_VERSION,
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        intended_evidence_unit_ref=request.intended_evidence_unit_ref,
        sampling_plan_ref=request.authoring_bundle.sampling_plan_ref,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        evidence_scope=construction.evidence_scope,
        case_state=state_payload.state,
        case_ref_binding=case_ref_binding,
        attempt_commitment_binding=attempt_binding,
        state_payload=state_payload,
        actor_policy_authority_ref=construction.policy_authority_ref,
        replacement_decision=replacement.value,
        audit_evidence_refs=construction.audit_evidence_refs,
        downstream_use_restrictions=construction.downstream_use_restrictions,
        disclosure_contract=construction.disclosure_contract,
    )
    disposition_ref = disposition.to_ref()
    graph = request.authoring_bundle.objects_by_ref()
    if material.artifact is not None:
        graph[material.artifact.case_ref] = material.artifact.case
    if (
        type(censoring_decision) is CensoringDecision
        and censoring_decision.censoring_record is not None
    ):
        graph[censoring_decision.censoring_record_ref] = (
            censoring_decision.censoring_record
        )
    graph[disposition_ref] = disposition
    try:
        validate_loaded_authoring_graph(graph)
    except (AuthoringError, TypeError, ValueError):
        graph_valid = False
    else:
        graph_valid = True
    if not graph_valid:
        raise _invalid("/disposition")
    return _record_pair_binding(disposition, disposition_ref)


def _terminal_reason(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    *,
    censoring_decision: CensoringDecision | None,
) -> object:
    if material.outcome_kind is GeneratorOutcomeKind.VALID_GENERATED:
        return TerminalReasonNotApplicable(
            _reason_ref(
                request,
                ApplicabilityReasonKind.TERMINAL_REASON_INAPPLICABLE,
            )
        )
    if material.outcome_kind is GeneratorOutcomeKind.REGISTERED_EXCLUSION:
        decision = material.support_decision
        if type(decision) is not SupportExclusionDecision:
            raise _incomplete("/support_decision")
        return TerminalReasonSupportDecision(decision, decision.to_ref())
    if material.outcome_kind is GeneratorOutcomeKind.CENSORED_CASE:
        if (
            type(censoring_decision) is not CensoringDecision
            or censoring_decision.censoring_record is None
            or censoring_decision.censoring_record_ref is None
        ):
            raise _incomplete("/censoring_decision")
        return TerminalReasonCensoringDecision(
            censoring_decision,
            censoring_decision.to_ref(),
            censoring_decision.censoring_record,
            censoring_decision.censoring_record_ref,
        )
    reason_pair = material.failure_reason_binding.pair
    occurrence_pair = material.failure_occurrence_binding.pair
    if reason_pair is None or occurrence_pair is None:
        raise _incomplete("/failure_reason_binding")
    return TerminalReasonFailure(
        reason_pair.record,
        reason_pair.ref,
        occurrence_pair.record,
        occurrence_pair.ref,
    )


def _material_after_accounting(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    decision: AttemptAccountingDecision,
) -> _TerminalMaterial:
    final = (decision.final_outcome, decision.final_stage)
    provisional = (material.outcome_kind, material.terminal_stage)
    if final == provisional:
        return material
    if final != (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
    ):
        raise _stale("/accounting_decision/final_terminal")
    return _terminal_material(
        request,
        material.source_event,
        outcome_kind=final[0],
        terminal_stage=final[1],
        applicability_stage=material.applicability_stage,
        payload_facts=material.payload_facts,
        support_decision=material.support_decision,
        artifact=material.artifact,
        censoring_request=material.censoring_request,
        censoring_verdict=material.censoring_verdict,
    )


def _finalize_censoring_if_available(
    material: _TerminalMaterial,
    *,
    directive: AttemptAccountingDirective,
    accounting_decision: AttemptAccountingDecision,
    accounting_decision_ref: object,
) -> CensoringDecision | None:
    if material.censoring_request is None or material.censoring_verdict is None:
        return None
    if (
        directive.directive_kind is AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE
        and material.censoring_verdict.verdict_kind is CensoringVerdictKind.CENSORED
    ):
        return None
    decision, _ = finalize_censoring_decision(
        request=material.censoring_request,
        verdict=material.censoring_verdict,
        verdict_ref=material.censoring_verdict.to_ref(),
        accounting_decision=accounting_decision,
        accounting_decision_ref=accounting_decision_ref,
    )
    return decision


def _case_result_binding(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> RecordRefBinding:
    if material.outcome_kind in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.CENSORED_CASE,
    }:
        if material.artifact is None:
            raise _incomplete("/artifact")
        return _record_pair_binding(material.artifact.case, material.artifact.case_ref)
    return _not_applicable_binding(
        request,
        ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
    )


def _attempt_case_binding(
    request: GeneratorRequest,
    material: _TerminalMaterial,
) -> ApplicabilityBinding[CanonicalChallengeCaseRef]:
    if material.outcome_kind in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.CENSORED_CASE,
    }:
        if material.artifact is None:
            raise _incomplete("/artifact")
        return ApplicabilityBinding.bound(material.artifact.case_ref)
    return ApplicabilityBinding.not_applicable(
        _reason_ref(
            request,
            ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
        )
    )


def _censoring_decision_binding(
    request: GeneratorRequest,
    decision: CensoringDecision | None,
) -> RecordRefBinding:
    if decision is None:
        return _not_applicable_binding(
            request,
            ApplicabilityReasonKind.CENSORING_DECISION_INAPPLICABLE,
        )
    return _record_pair_binding(decision, decision.to_ref())


def _build_final_result(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    *,
    accounting_decision: AttemptAccountingDecision,
    accounting_decision_ref: object,
    conformance_facts: object,
    conformance_facts_ref: object,
    censoring_decision: CensoringDecision | None,
    attempt_record: GenerationAttemptRecord,
    attempt_record_ref: object,
) -> GeneratorResult:
    censoring_binding = _censoring_decision_binding(request, censoring_decision)
    disposition_binding = _disposition_binding(
        request,
        material,
        accounting_decision=accounting_decision,
        attempt_record_ref=attempt_record_ref,
        conformance_ref=conformance_facts_ref,
        censoring_decision=censoring_decision,
    )
    record = GeneratorResultRecord(
        challenge_key=request.challenge_key,
        physical_system_ref=request.authoring_bundle.physical_system_ref,
        candidate_output_ref=request.authoring_bundle.candidate_output_ref,
        primary_population_ref=request.authoring_bundle.primary_population_ref,
        selection_population_ref=request.authoring_bundle.selection_population_ref,
        sampling_plan_ref=request.authoring_bundle.sampling_plan_ref,
        generator_ref=request.generator_ref,
        environment_ref=request.environment_ref,
        fixture_configuration_ref=request.fixture_configuration_ref,
        role_binding=request.role_binding,
        fixture_registration_ref=request.generator.fixture_registration_ref,
        source_provenance_refs=request.generator.source_provenance_refs,
        request_ref=request.to_ref(),
        source_event=material.source_event,
        source_event_ref=material.source_event.to_ref(),
        outcome_kind=material.outcome_kind,
        terminal_stage=material.terminal_stage,
        case_binding=_case_result_binding(request, material),
        constructed_case_binding=_artifact_binding(request, material.artifact),
        support_decision_binding=_support_binding(
            request,
            material.support_decision,
        ),
        censoring_verdict_binding=_censoring_verdict_binding(
            request,
            material.censoring_verdict,
        ),
        censoring_decision_binding=censoring_binding,
        disposition_binding=disposition_binding,
        terminal_reason_binding=_terminal_reason(
            request,
            material,
            censoring_decision=censoring_decision,
        ),
        attempt_accounting_decision=accounting_decision,
        attempt_accounting_decision_ref=accounting_decision_ref,
        attempt_record=attempt_record,
        attempt_record_ref=attempt_record_ref,
        conformance_facts=conformance_facts,
        conformance_facts_ref=conformance_facts_ref,
    )
    return GeneratorResult(record, record.to_ref(), material.artifact)


def _terminalize(
    request: GeneratorRequest,
    material: _TerminalMaterial,
    accounting_authority: object,
) -> GeneratorInvocationOutput:
    accounting_request = build_attempt_accounting_request(request, material)
    directive, directive_ref = decide_attempt_accounting(
        accounting_request,
        accounting_authority,
    )
    if directive.directive_kind is AttemptAccountingDirectiveKind.PENDING_SUCCESSOR:
        conformance, conformance_ref = _conformance_for(request, material)
        pending = build_pending_generation_attempt(
            request=accounting_request,
            directive=directive,
            directive_ref=directive_ref,
            conformance_facts=conformance,
            conformance_facts_ref=conformance_ref,
            artifact=material.artifact,
        )
        return GeneratorInvocationOutput.pending_successor(pending)

    accounting_decision, accounting_decision_ref = build_attempt_accounting_decision(
        request=accounting_request,
        directive=directive,
        directive_ref=directive_ref,
    )
    final_material = _material_after_accounting(
        request,
        material,
        accounting_decision,
    )
    conformance, conformance_ref = _conformance_for(request, final_material)
    censoring_decision = _finalize_censoring_if_available(
        material,
        directive=directive,
        accounting_decision=accounting_decision,
        accounting_decision_ref=accounting_decision_ref,
    )
    censoring_binding = _censoring_decision_binding(
        request,
        censoring_decision,
    )
    attempt_record, attempt_record_ref = build_generation_attempt_record(
        request=request,
        source_event=final_material.source_event,
        accounting_decision=accounting_decision,
        accounting_decision_ref=accounting_decision_ref,
        case_ref_binding=_attempt_case_binding(request, final_material),
        support_decision_binding=_support_binding(
            request,
            final_material.support_decision,
        ),
        censoring_verdict_binding=_censoring_verdict_binding(
            request,
            final_material.censoring_verdict,
        ),
        censoring_decision_binding=censoring_binding,
        conformance_facts_pair=RecordRefPair(conformance, conformance_ref),
        failure_reason_binding=final_material.failure_reason_binding,
        failure_occurrence_binding=final_material.failure_occurrence_binding,
        pending_attempt_binding=ApplicabilityBinding.not_applicable(
            _reason_ref(
                request,
                ApplicabilityReasonKind.PENDING_ATTEMPT_INAPPLICABLE,
            )
        ),
    )
    result = _build_final_result(
        request,
        final_material,
        accounting_decision=accounting_decision,
        accounting_decision_ref=accounting_decision_ref,
        conformance_facts=conformance,
        conformance_facts_ref=conformance_ref,
        censoring_decision=censoring_decision,
        attempt_record=attempt_record,
        attempt_record_ref=attempt_record_ref,
    )
    return GeneratorInvocationOutput.final(result)


def generate_fixture_case(
    request: object,
    *,
    fixture_authority: object,
    support_authority: object,
    censoring_authority: object,
    accounting_authority: object,
) -> GeneratorInvocationOutput:
    """Execute exactly one admitted B-03 fixture attempt with no retry loop."""

    admitted = validate_generator_request(
        request,
        fixture_authority=fixture_authority,
        support_authority=support_authority,
        censoring_authority=censoring_authority,
        accounting_authority=accounting_authority,
    )
    assert type(admitted) is GeneratorRequest
    # Every path after admission belongs to this exact attempt.  Claim it
    # before compatibility work can terminate so the same request cannot
    # create a second event, result, or accounting row.
    fixture_authority.claim_attempt(admitted)
    try:
        validate_candidate_against_physical(
            admitted.authoring_bundle.candidate_output,
            admitted.authoring_bundle.physical_system,
        )
    except (AuthoringError, TypeError, ValueError):
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.INVALID_CONSTRUCTION,
                terminal_stage=(GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY),
                not_attempted=True,
            ),
            accounting_authority,
        )

    try:
        grant = fixture_authority.issue_grant(admitted)
        grant = fixture_authority.validate_grant(admitted, grant)
    except Exception:  # noqa: BLE001 - provider/capability boundary
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                terminal_stage=GeneratorTerminalStage.CONTEXT_ACQUISITION,
            ),
            accounting_authority,
        )

    try:
        derived_seed = grant.derive_once(admitted.role_binding)
    except Exception:  # noqa: BLE001 - protected derivation boundary
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                terminal_stage=GeneratorTerminalStage.DERIVATION,
            ),
            accounting_authority,
        )
    try:
        payload = _materialize_burgers_fixture_payload(
            derived_seed,
            fixture_configuration_ref=admitted.fixture_configuration_ref,
        )
    except (GeneratorValidationError, TypeError, ValueError):
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
                terminal_stage=GeneratorTerminalStage.MATERIALIZATION,
            ),
            accounting_authority,
        )
    except Exception:  # noqa: BLE001 - internal materializer infrastructure split
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                terminal_stage=GeneratorTerminalStage.MATERIALIZATION,
            ),
            accounting_authority,
        )
    finally:
        del derived_seed

    try:
        materialized = _materialized_from_payload(admitted, payload)
    except (GeneratorValidationError, TypeError, ValueError):
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
                terminal_stage=GeneratorTerminalStage.MATERIALIZATION,
            ),
            accounting_authority,
        )
    except Exception:  # noqa: BLE001 - protected codec infrastructure split
        return _terminalize(
            admitted,
            _no_payload_material(
                admitted,
                outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                terminal_stage=GeneratorTerminalStage.MATERIALIZATION,
            ),
            accounting_authority,
        )

    support_decision = assess_support_exclusion(
        admitted,
        materialized,
        support_authority,
    )
    support_terminal = _support_terminal_material(
        admitted,
        materialized,
        support_decision,
    )
    if support_terminal is not None:
        return _terminalize(
            admitted,
            support_terminal,
            accounting_authority,
        )

    try:
        case = build_generated_case(
            admitted,
            source_event=materialized.source_event,
            payload_ref=materialized.payload_ref,
        )
    except (AuthoringError, TypeError, ValueError):
        material = _terminal_material(
            admitted,
            materialized.source_event,
            outcome_kind=GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            terminal_stage=GeneratorTerminalStage.CASE_CONSTRUCTION,
            payload_facts=materialized.payload_facts,
            support_decision=support_decision,
        )
        return _terminalize(admitted, material, accounting_authority)
    except Exception:  # noqa: BLE001 - case-construction infrastructure split
        material = _terminal_material(
            admitted,
            materialized.source_event,
            outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
            terminal_stage=GeneratorTerminalStage.CASE_CONSTRUCTION,
            payload_facts=materialized.payload_facts,
            support_decision=support_decision,
        )
        return _terminalize(admitted, material, accounting_authority)

    try:
        artifact = build_generated_artifact(
            admitted,
            grant=grant,
            case=case,
        )
    except (AuthoringError, TypeError, ValueError):
        material = _terminal_material(
            admitted,
            materialized.source_event,
            outcome_kind=GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            terminal_stage=GeneratorTerminalStage.GRAPH_VALIDATION,
            payload_facts=materialized.payload_facts,
            support_decision=support_decision,
        )
        return _terminalize(admitted, material, accounting_authority)
    except Exception:  # noqa: BLE001 - graph-validation infrastructure split
        material = _terminal_material(
            admitted,
            materialized.source_event,
            outcome_kind=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
            terminal_stage=GeneratorTerminalStage.GRAPH_VALIDATION,
            payload_facts=materialized.payload_facts,
            support_decision=support_decision,
        )
        return _terminalize(admitted, material, accounting_authority)

    material = _validated_terminal_material(
        admitted,
        materialized,
        support_decision,
        artifact,
        censoring_authority,
    )
    output = _terminalize(admitted, material, accounting_authority)
    if type(
        output.payload
    ) is GeneratorResult and output.payload.record.outcome_kind in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.CENSORED_CASE,
    }:
        fixture_authority.register_replay_baseline(admitted, output.payload)
    return output


def finalize_pending_generation_attempt(
    *,
    predecessor_request: GeneratorRequest,
    pending: PendingGenerationAttempt,
    successor_request: GeneratorRequest,
    successor_output: GeneratorInvocationOutput,
) -> GeneratorResult:
    """Purely finalize one predecessor after its exact successor has executed."""

    if type(successor_output) is not GeneratorInvocationOutput:
        raise _wrong("/successor_output")
    malformed_successor = False
    try:
        checked_successor_output = GeneratorInvocationOutput(
            successor_output.kind,
            successor_output.payload,
        )
    except AttributeError:
        malformed_successor = True
        checked_successor_output = None
    if malformed_successor:
        raise _wrong("/successor_output")
    decision, decision_ref, censoring, censoring_ref, attempt, attempt_ref = (
        finalize_pending_accounting(
            predecessor_request=predecessor_request,
            pending=pending,
            successor_request=successor_request,
            successor_output=checked_successor_output.payload,
        )
    )
    del censoring_ref
    record = pending.record
    conformance_pair = record.conformance_facts_pair
    payload_binding = conformance_pair.record.payload_facts_binding
    payload_facts = payload_binding.value if payload_binding.is_bound else None
    support_decision = (
        record.support_decision_binding.pair.record
        if record.support_decision_binding.is_bound
        else None
    )
    verdict = (
        record.censoring_verdict_binding.pair.record
        if record.censoring_verdict_binding.is_bound
        else None
    )
    material = _TerminalMaterial(
        source_event=record.source_event_pair.record,
        outcome_kind=record.provisional_outcome,
        terminal_stage=record.provisional_stage,
        applicability_stage=record.provisional_stage,
        payload_facts=payload_facts,
        support_decision=support_decision,
        artifact=pending.artifact,
        censoring_request=None if verdict is None else verdict.request,
        censoring_verdict=verdict,
        failure_reason_binding=record.failure_reason_binding,
        failure_occurrence_binding=record.failure_occurrence_binding,
    )
    if (decision.final_outcome, decision.final_stage) != (
        material.outcome_kind,
        material.terminal_stage,
    ):
        raise _stale("/accounting_decision/final_terminal")
    return _build_final_result(
        predecessor_request,
        material,
        accounting_decision=decision,
        accounting_decision_ref=decision_ref,
        conformance_facts=conformance_pair.record,
        conformance_facts_ref=conformance_pair.ref,
        censoring_decision=(
            censoring if type(censoring) is CensoringDecision else None
        ),
        attempt_record=attempt,
        attempt_record_ref=attempt_ref,
    )


__all__ = [
    "assess_support_exclusion",
    "build_attempt_accounting_request",
    "build_censoring_request",
    "build_generated_artifact",
    "build_generated_case",
    "build_generation_source_event",
    "build_support_exclusion_request",
    "burgers_fixture_implementation_manifest",
    "decide_attempt_accounting",
    "decide_censoring",
    "failure_occurrence",
    "finalize_pending_generation_attempt",
    "generate_fixture_case",
    "support_terminal_classification",
    "validate_generator_request",
]
