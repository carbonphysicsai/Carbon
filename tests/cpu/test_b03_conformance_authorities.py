"""Nominal post-result and post-accounting conformance authority boundaries."""

from __future__ import annotations

from dataclasses import replace

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.authoring.canonical import (
    CanonicalText,
    encode_value,
    owner_ref_to_canonical,
)
from carbon.authoring.loading import GraphOriginTag
from carbon.authoring.model import ApplicabilityBinding
from carbon.generators.accounting import (
    build_generation_accounting_summary,
    build_intended_unit_accounting,
)
from carbon.generators.canonical import (
    canonical_bytes,
    canonical_content_digest,
    decode_canonical_bytes,
)
from carbon.generators.conformance import (
    ComparisonCorpusAvailability,
    ComparisonCorpusDecision,
    ExternalDistributionFactDecision,
    ExternalDistributionFactKind,
    ExternalDistributionFactSet,
    ExternalFactAvailability,
    ExternalFactAvailabilityKind,
    GeneratorConformanceFacts,
    NearDuplicateDecision,
    NearDuplicateDecisionKind,
    build_duplicate_conformance_facts,
    build_external_distribution_fact_request,
    build_external_distribution_fact_set,
    build_near_duplicate_request,
    build_post_result_duplicate_request,
    decide_comparison_corpus,
    decide_external_distribution_fact,
    decide_near_duplicate,
)
from carbon.generators.errors import GeneratorValidationError
from carbon.generators.model import (
    GeneratorOutcomeKind,
    GeneratorTerminalStage,
    RecordRefPair,
)
from carbon.generators.service import generate_fixture_case
from carbon.registry.model import ChallengeKey

_SECRET = "secret-authority-value-at-private-path"


class _HostileAuthorityError(RuntimeError):
    pass


def _constructor_bypass(value: object, **updates: object) -> object:
    forged = object.__new__(type(value))
    for field_name in value.__dataclass_fields__:
        object.__setattr__(
            forged,
            field_name,
            updates.get(field_name, getattr(value, field_name)),
        )
    return forged


def _other_challenge_owner(kind: str, object_id: str) -> object:
    return challenge_owner(
        kind,
        object_id,
        challenge_key=ChallengeKey("b03_other_challenge", "1.0"),
    )


def _generated_subject(**fixture_options: object):
    fixture = make_b03_fixture(**fixture_options)
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    return fixture, output.payload


def _post_result_request():
    _, result = _generated_subject()
    return build_post_result_duplicate_request(
        subject_result=result,
        corpus_owner_unavailable_reason_ref=challenge_owner(
            "applicability_reason",
            "comparison_corpus_owner_unavailable",
        ),
        near_duplicate_policy_unavailable_reason_ref=challenge_owner(
            "applicability_reason",
            "near_duplicate_policy_unavailable",
        ),
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "case_ref",
        "representation_ref",
        "physical_payload_ref",
        "primary_population_ref",
        "sampling_plan_ref",
        "graph_origin",
        "origin_evidence_refs",
        "composition_audit_ref",
    ),
)
def test_conformance_rejects_validated_artifact_fact_not_bound_to_request(
    field_name: str,
) -> None:
    _, result = _generated_subject()
    facts = result.record.conformance_facts
    validated = facts.validated_case_facts_binding.value
    updates = {
        "case_ref": replace(
            validated.case_ref,
            object_id="forged_generated_case",
        ),
        "representation_ref": challenge_owner(
            "representation",
            "forged_case_representation",
        ),
        "physical_payload_ref": challenge_owner(
            "protected_case_payload",
            "forged_case_payload",
        ),
        "primary_population_ref": facts.selection_population_ref,
        "sampling_plan_ref": replace(
            validated.sampling_plan_ref,
            object_id="forged_sampling_plan",
        ),
        "graph_origin": GraphOriginTag.DRAFT_OR_UNRESOLVED,
        "origin_evidence_refs": (
            challenge_owner(
                "authoring_origin_evidence",
                "forged_case_origin",
            ),
            *validated.origin_evidence_refs[1:],
        ),
        "composition_audit_ref": challenge_owner(
            "origin_composition_audit",
            "forged_case_composition",
        ),
    }
    forged_validated = _constructor_bypass(
        validated,
        **{field_name: updates[field_name]},
    )
    forged_binding = ApplicabilityBinding.bound(forged_validated)

    with pytest.raises(GeneratorValidationError):
        replace(
            facts.replay_identity_facts,
            constructed_case_facts_binding=forged_binding,
        )

    forged_replay = _constructor_bypass(
        facts.replay_identity_facts,
        constructed_case_facts_binding=forged_binding,
    )
    with pytest.raises(GeneratorValidationError):
        replace(
            facts,
            validated_case_facts_binding=forged_binding,
            replay_identity_facts=forged_replay,
        )

    forged_facts = _constructor_bypass(
        facts,
        validated_case_facts_binding=forged_binding,
        replay_identity_facts=forged_replay,
    )
    with pytest.raises(GeneratorValidationError):
        decode_canonical_bytes(
            canonical_bytes(forged_facts),
            GeneratorConformanceFacts,
        )


def test_conformance_rejects_payload_fingerprint_representation_not_bound_to_request() -> (
    None
):
    _, result = _generated_subject()
    facts = result.record.conformance_facts
    payload = facts.payload_facts_binding.value
    fingerprint = _constructor_bypass(
        payload.physical_payload_fingerprint,
        case_representation_ref=challenge_owner(
            "representation",
            "forged_payload_representation",
        ),
    )
    forged_payload = _constructor_bypass(
        payload,
        physical_payload_fingerprint=fingerprint,
        physical_payload_fingerprint_ref=fingerprint.to_ref(),
    )
    forged_binding = ApplicabilityBinding.bound(forged_payload)

    with pytest.raises(GeneratorValidationError):
        replace(
            facts.replay_identity_facts,
            payload_facts_binding=forged_binding,
        )

    forged_replay = _constructor_bypass(
        facts.replay_identity_facts,
        payload_facts_binding=forged_binding,
    )
    with pytest.raises(GeneratorValidationError):
        replace(
            facts,
            payload_facts_binding=forged_binding,
            replay_identity_facts=forged_replay,
        )

    forged_facts = _constructor_bypass(
        facts,
        payload_facts_binding=forged_binding,
        replay_identity_facts=forged_replay,
    )
    with pytest.raises(GeneratorValidationError):
        decode_canonical_bytes(
            canonical_bytes(forged_facts),
            GeneratorConformanceFacts,
        )


def _bound_corpus_decision(request):
    return ComparisonCorpusDecision(
        request=request,
        availability=ComparisonCorpusAvailability.BOUND,
        corpus_results=(),
        corpus_issuance_ref=challenge_owner(
            "authority_evidence",
            "empty_comparison_corpus_issuance",
        ),
        unavailable_reason_ref=None,
    )


def test_duplicate_facts_derive_exact_collisions_and_unavailable_bindings() -> None:
    _, subject = _generated_subject()
    _, duplicate = _generated_subject(censoring_mode="censored")
    request = build_post_result_duplicate_request(
        subject_result=subject,
        corpus_owner_unavailable_reason_ref=challenge_owner(
            "applicability_reason",
            "comparison_corpus_owner_unavailable",
        ),
        near_duplicate_policy_unavailable_reason_ref=challenge_owner(
            "applicability_reason",
            "near_duplicate_policy_unavailable",
        ),
    )
    duplicate_decision = ComparisonCorpusDecision(
        request=request,
        availability=ComparisonCorpusAvailability.BOUND,
        corpus_results=(RecordRefPair(duplicate.record, duplicate.ref),),
        corpus_issuance_ref=challenge_owner(
            "authority_evidence",
            "duplicate_comparison_corpus_issuance",
        ),
        unavailable_reason_ref=None,
    )
    near_request = build_near_duplicate_request(
        post_result_request=request,
        corpus_decision=duplicate_decision,
        corpus_decision_ref=duplicate_decision.to_ref(),
        duplicate_rule_ref=challenge_owner(
            "duplicate_rule",
            "external_duplicate_rule",
        ),
        semantic_equivalence_ref=challenge_owner(
            "semantic_equivalence",
            "external_semantic_equivalence",
        ),
    )
    near = _bound_near_decision(near_request)
    duplicate_facts, duplicate_facts_ref = build_duplicate_conformance_facts(
        post_result_request=request,
        corpus_decision=duplicate_decision,
        corpus_decision_ref=duplicate_decision.to_ref(),
        near_duplicate_decision=near,
    )

    assert duplicate_facts.canonical_case_duplicate_binding.value is True
    assert duplicate_facts.physical_instance_collision_binding.value is True
    assert duplicate_facts.near_duplicate_decision_binding.value == near
    assert duplicate_facts_ref == duplicate_facts.to_ref()

    distinct_fixture = make_b03_fixture()
    distinct_request = replace(
        distinct_fixture.request,
        case_construction=replace(
            distinct_fixture.request.case_construction,
            object_id="burgers_generated_case_distinct",
        ),
    )
    distinct = generate_fixture_case(
        distinct_request,
        fixture_authority=distinct_fixture.fixture_authority,
        support_authority=distinct_fixture.support_authority,
        censoring_authority=distinct_fixture.censoring_authority,
        accounting_authority=distinct_fixture.accounting_authority,
    ).payload
    assert distinct.artifact.case_ref != subject.artifact.case_ref
    assert (
        distinct.record.conformance_facts.payload_facts_binding.value.physical_payload_fingerprint_ref
        == subject.record.conformance_facts.payload_facts_binding.value.physical_payload_fingerprint_ref
    )
    mixed_decision = ComparisonCorpusDecision(
        request=request,
        availability=ComparisonCorpusAvailability.BOUND,
        corpus_results=(RecordRefPair(distinct.record, distinct.ref),),
        corpus_issuance_ref=challenge_owner(
            "authority_evidence",
            "mixed_comparison_corpus_issuance",
        ),
        unavailable_reason_ref=None,
    )
    mixed_near_request = build_near_duplicate_request(
        post_result_request=request,
        corpus_decision=mixed_decision,
        corpus_decision_ref=mixed_decision.to_ref(),
        duplicate_rule_ref=near_request.duplicate_rule_ref,
        semantic_equivalence_ref=near_request.semantic_equivalence_ref,
    )
    mixed_facts, _ = build_duplicate_conformance_facts(
        post_result_request=request,
        corpus_decision=mixed_decision,
        corpus_decision_ref=mixed_decision.to_ref(),
        near_duplicate_decision=_bound_near_decision(mixed_near_request),
    )
    assert mixed_facts.canonical_case_duplicate_binding.value is False
    assert mixed_facts.physical_instance_collision_binding.value is True

    empty_decision = _bound_corpus_decision(request)
    empty_near_request = build_near_duplicate_request(
        post_result_request=request,
        corpus_decision=empty_decision,
        corpus_decision_ref=empty_decision.to_ref(),
        duplicate_rule_ref=near_request.duplicate_rule_ref,
        semantic_equivalence_ref=near_request.semantic_equivalence_ref,
    )
    empty_near = _bound_near_decision(empty_near_request)
    distinct_facts, _ = build_duplicate_conformance_facts(
        post_result_request=request,
        corpus_decision=empty_decision,
        corpus_decision_ref=empty_decision.to_ref(),
        near_duplicate_decision=empty_near,
    )
    assert distinct_facts.canonical_case_duplicate_binding.value is False
    assert distinct_facts.physical_instance_collision_binding.value is False

    unavailable = ComparisonCorpusDecision(
        request=request,
        availability=ComparisonCorpusAvailability.OWNER_UNAVAILABLE,
        corpus_results=(),
        corpus_issuance_ref=None,
        unavailable_reason_ref=request.corpus_owner_unavailable_reason_ref,
    )
    unavailable_facts, _ = build_duplicate_conformance_facts(
        post_result_request=request,
        corpus_decision=unavailable,
        corpus_decision_ref=unavailable.to_ref(),
        near_duplicate_decision=None,
    )
    for binding in (
        unavailable_facts.duplicate_comparison_request_binding,
        unavailable_facts.canonical_case_duplicate_binding,
        unavailable_facts.physical_instance_collision_binding,
        unavailable_facts.near_duplicate_decision_binding,
    ):
        assert not binding.is_bound
        assert binding.value == request.corpus_owner_unavailable_reason_ref

    forged_near = _constructor_bypass(
        near,
        fact_ref=_other_challenge_owner(
            "evidence_artifact",
            "forged_nested_near_fact",
        ),
    )
    with pytest.raises(GeneratorValidationError):
        build_duplicate_conformance_facts(
            post_result_request=request,
            corpus_decision=duplicate_decision,
            corpus_decision_ref=duplicate_decision.to_ref(),
            near_duplicate_decision=forged_near,
        )


def test_duplicate_authority_values_reject_cloned_subclasses() -> None:
    request = _post_result_request()
    decision = _bound_corpus_decision(request)

    for value in (request, decision):

        class ClonedSubclass(type(value)):
            pass

        with pytest.raises(GeneratorValidationError):
            ClonedSubclass(
                **{
                    field_name: getattr(value, field_name)
                    for field_name in value.__dataclass_fields__
                }
            )


def _forged_corpus_result_pair(request):
    forged_record = _constructor_bypass(
        request.subject_result,
        terminal_stage=GeneratorTerminalStage.CONTEXT_ACQUISITION,
    )
    forged_ref = replace(
        request.subject_result_ref,
        content_digest=canonical_content_digest(forged_record),
    )
    return RecordRefPair(forged_record, forged_ref)


class _CorpusAuthority:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    def decide_comparison_corpus(self, request):
        self.calls += 1
        if self.mode == "exception":
            raise _HostileAuthorityError(_SECRET)
        if self.mode == "partial":
            return object()
        if self.mode == "stale_echo":
            stale_request = replace(
                request,
                corpus_owner_unavailable_reason_ref=challenge_owner(
                    "applicability_reason",
                    "stale_corpus_owner_unavailable",
                ),
            )
            return ComparisonCorpusDecision(
                request=stale_request,
                availability=ComparisonCorpusAvailability.OWNER_UNAVAILABLE,
                corpus_results=(),
                corpus_issuance_ref=None,
                unavailable_reason_ref=(
                    stale_request.corpus_owner_unavailable_reason_ref
                ),
            )
        if self.mode == "subclass":

            class CorpusDecisionSubclass(ComparisonCorpusDecision):
                pass

            return CorpusDecisionSubclass(
                request=request,
                availability=ComparisonCorpusAvailability.BOUND,
                corpus_results=(),
                corpus_issuance_ref=challenge_owner(
                    "authority_evidence",
                    "subclass_corpus_issuance",
                ),
                unavailable_reason_ref=None,
            )
        if self.mode == "forged_member":
            return _constructor_bypass(
                _bound_corpus_decision(request),
                corpus_results=(_forged_corpus_result_pair(request),),
            )
        return _bound_corpus_decision(request)


def test_comparison_corpus_authority_accepts_one_exact_response() -> None:
    request = _post_result_request()
    authority = _CorpusAuthority("exact")

    decision, decision_ref = decide_comparison_corpus(request, authority)

    assert authority.calls == 1
    assert decision.request == request
    assert decision.availability is ComparisonCorpusAvailability.BOUND
    assert decision_ref == decision.to_ref()


@pytest.mark.parametrize(
    "mode",
    ("exception", "partial", "stale_echo", "subclass", "forged_member"),
)
def test_comparison_corpus_hostility_fails_closed_once(mode: str) -> None:
    request = _post_result_request()
    authority = _CorpusAuthority(mode)

    decision, decision_ref = decide_comparison_corpus(request, authority)

    assert authority.calls == 1
    assert decision.request == request
    assert decision.availability is ComparisonCorpusAvailability.OWNER_UNAVAILABLE
    assert decision.corpus_results == ()
    assert decision.corpus_issuance_ref is None
    assert (
        decision.unavailable_reason_ref == request.corpus_owner_unavailable_reason_ref
    )
    assert decision_ref == decision.to_ref()
    assert _SECRET not in repr(decision)
    assert _SECRET.encode() not in decision.canonical_bytes()


def test_comparison_corpus_constructor_rejects_bypassed_result_member() -> None:
    request = _post_result_request()

    with pytest.raises(GeneratorValidationError):
        ComparisonCorpusDecision(
            request=request,
            availability=ComparisonCorpusAvailability.BOUND,
            corpus_results=(_forged_corpus_result_pair(request),),
            corpus_issuance_ref=challenge_owner(
                "authority_evidence",
                "forged_comparison_corpus_issuance",
            ),
            unavailable_reason_ref=None,
        )


def _near_duplicate_request():
    post_result_request = _post_result_request()
    corpus_decision = _bound_corpus_decision(post_result_request)
    return build_near_duplicate_request(
        post_result_request=post_result_request,
        corpus_decision=corpus_decision,
        corpus_decision_ref=corpus_decision.to_ref(),
        duplicate_rule_ref=challenge_owner(
            "duplicate_rule",
            "external_duplicate_rule",
        ),
        semantic_equivalence_ref=challenge_owner(
            "semantic_equivalence",
            "external_semantic_equivalence",
        ),
    )


def _bound_near_decision(request):
    return NearDuplicateDecision(
        request=request,
        decision_kind=NearDuplicateDecisionKind.DISTINCT,
        semantic_equivalence_ref=request.semantic_equivalence_ref,
        fact_ref=challenge_owner("evidence_artifact", "near_duplicate_fact"),
        audit_evidence_ref=challenge_owner(
            "audit_evidence",
            "near_duplicate_audit",
        ),
        duplicate_rule_ref=None,
        unavailable_reason_ref=None,
    )


class _NearDuplicateAuthority:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    def decide_near_duplicate(self, request):
        self.calls += 1
        if self.mode == "exception":
            raise _HostileAuthorityError(_SECRET)
        if self.mode == "partial":
            return object()
        decision = _bound_near_decision(request)
        if self.mode == "wrong_policy":
            return _constructor_bypass(
                decision,
                semantic_equivalence_ref=challenge_owner(
                    "semantic_equivalence",
                    "wrong_semantic_equivalence",
                ),
            )
        if self.mode == "cross_challenge":
            return _constructor_bypass(
                decision,
                fact_ref=_other_challenge_owner(
                    "evidence_artifact",
                    "cross_challenge_near_fact",
                ),
            )
        return decision


def test_near_duplicate_authority_accepts_one_exact_response() -> None:
    request = _near_duplicate_request()
    authority = _NearDuplicateAuthority("exact")

    decision = decide_near_duplicate(request, authority)

    assert authority.calls == 1
    assert decision.request == request
    assert decision.decision_kind is NearDuplicateDecisionKind.DISTINCT
    assert decision.semantic_equivalence_ref == request.semantic_equivalence_ref


@pytest.mark.parametrize(
    "mode",
    ("exception", "partial", "wrong_policy", "cross_challenge"),
)
def test_near_duplicate_hostility_fails_closed_once(mode: str) -> None:
    request = _near_duplicate_request()
    authority = _NearDuplicateAuthority(mode)

    decision = decide_near_duplicate(request, authority)

    assert authority.calls == 1
    assert decision.request == request
    assert decision.decision_kind is NearDuplicateDecisionKind.POLICY_UNAVAILABLE
    assert decision.duplicate_rule_ref == request.duplicate_rule_ref
    assert decision.semantic_equivalence_ref == request.semantic_equivalence_ref
    assert decision.unavailable_reason_ref == request.policy_unavailable_reason_ref
    assert decision.fact_ref is None
    assert decision.audit_evidence_ref is None
    assert _SECRET not in repr(decision)


def _external_fact_request():
    fixture, result = _generated_subject()
    record = result.record
    accounting_decision = record.attempt_accounting_decision
    directive_pair = accounting_decision.accounting_directive_pair
    unit, unit_ref = build_intended_unit_accounting(
        link_decision_pairs=(
            RecordRefPair(
                fixture.request.intended_unit_link_decision,
                fixture.request.intended_unit_link_decision_ref,
            ),
        ),
        attempt_record_pairs=(
            RecordRefPair(record.attempt_record, record.attempt_record_ref),
        ),
        pending_attempt_pairs=(),
        accounting_directive_pairs=(directive_pair,),
        accounting_decision_pairs=(
            RecordRefPair(
                accounting_decision,
                record.attempt_accounting_decision_ref,
            ),
        ),
    )
    unit_pair = RecordRefPair(unit, unit_ref)
    summary, summary_ref = build_generation_accounting_summary((unit_pair,))
    return build_external_distribution_fact_request(
        result_pairs=(RecordRefPair(record, result.ref),),
        intended_unit_pairs=(unit_pair,),
        accounting_summary=summary,
        accounting_summary_ref=summary_ref,
        requested_fact_kind=ExternalDistributionFactKind.MARGINAL,
        statistics_objective_ref=challenge_owner(
            "statistics_objective",
            "external_marginal_objective",
        ),
        owner_unavailable_reason_ref=challenge_owner(
            "applicability_reason",
            "external_fact_owner_unavailable",
        ),
    )


def _bound_external_decision(request):
    return ExternalDistributionFactDecision(
        request=request,
        availability=ExternalFactAvailability(
            availability=ExternalFactAvailabilityKind.BOUND,
            fact_kind=request.requested_fact_kind,
            statistics_objective_ref=None,
            fact_ref=challenge_owner("evidence_artifact", "external_fact"),
            audit_evidence_ref=challenge_owner(
                "audit_evidence",
                "external_fact_audit",
            ),
            unavailable_reason_ref=None,
        ),
    )


class _ExternalFactAuthority:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    def decide_external_distribution_fact(self, request):
        self.calls += 1
        if self.mode == "exception":
            raise _HostileAuthorityError(_SECRET)
        if self.mode == "partial":
            return object()
        decision = _bound_external_decision(request)
        if self.mode == "wrong_fact_kind":
            availability = replace(
                decision.availability,
                fact_kind=ExternalDistributionFactKind.JOINT,
            )
            return _constructor_bypass(decision, availability=availability)
        if self.mode == "cross_challenge":
            availability = replace(
                decision.availability,
                fact_ref=_other_challenge_owner(
                    "evidence_artifact",
                    "cross_challenge_external_fact",
                ),
            )
            return _constructor_bypass(decision, availability=availability)
        return decision


def test_external_fact_authority_accepts_one_exact_response() -> None:
    request = _external_fact_request()
    authority = _ExternalFactAuthority("exact")

    decision = decide_external_distribution_fact(request, authority)

    assert authority.calls == 1
    assert decision.request == request
    assert decision.availability.availability is ExternalFactAvailabilityKind.BOUND
    assert decision.availability.fact_kind is request.requested_fact_kind


@pytest.mark.parametrize(
    "mode",
    ("exception", "partial", "wrong_fact_kind", "cross_challenge"),
)
def test_external_fact_hostility_fails_closed_once(mode: str) -> None:
    request = _external_fact_request()
    authority = _ExternalFactAuthority(mode)

    decision = decide_external_distribution_fact(request, authority)

    assert authority.calls == 1
    availability = decision.availability
    assert decision.request == request
    assert availability.availability is ExternalFactAvailabilityKind.OWNER_UNAVAILABLE
    assert availability.statistics_objective_ref == request.statistics_objective_ref
    assert availability.unavailable_reason_ref == request.owner_unavailable_reason_ref
    assert availability.fact_kind is None
    assert availability.fact_ref is None
    assert availability.audit_evidence_ref is None
    assert _SECRET not in repr(decision)


def test_external_fact_set_uses_exact_encoded_fact_and_objective_order() -> None:
    marginal_request = _external_fact_request()
    joint_request = replace(
        marginal_request,
        requested_fact_kind=ExternalDistributionFactKind.JOINT,
        statistics_objective_ref=challenge_owner(
            "statistics_objective",
            "external_joint_objective",
        ),
    )
    tail_request = replace(
        marginal_request,
        requested_fact_kind=ExternalDistributionFactKind.TAIL_ALLOCATION,
        statistics_objective_ref=challenge_owner(
            "statistics_objective",
            "external_tail_objective",
        ),
    )
    supplied = (
        _bound_external_decision(marginal_request),
        _bound_external_decision(tail_request),
        _bound_external_decision(joint_request),
    )

    fact_set, fact_set_ref = build_external_distribution_fact_set(supplied)

    def encoded_key(decision):
        request = decision.request
        return (
            encode_value(CanonicalText(request.requested_fact_kind.value)),
            encode_value(owner_ref_to_canonical(request.statistics_objective_ref)),
        )

    expected = tuple(sorted(supplied, key=encoded_key))
    assert fact_set.decisions == expected
    assert fact_set_ref == fact_set.to_ref()
    assert expected != supplied
    with pytest.raises(GeneratorValidationError):
        ExternalDistributionFactSet(
            challenge_key=fact_set.challenge_key,
            result_pairs=fact_set.result_pairs,
            intended_unit_pairs=fact_set.intended_unit_pairs,
            accounting_summary=fact_set.accounting_summary,
            accounting_summary_ref=fact_set.accounting_summary_ref,
            sampling_plan_ref=fact_set.sampling_plan_ref,
            primary_population_ref=fact_set.primary_population_ref,
            selection_population_ref=fact_set.selection_population_ref,
            decisions=tuple(reversed(fact_set.decisions)),
        )

    forged_availability = _constructor_bypass(
        supplied[0].availability,
        fact_kind=ExternalDistributionFactKind.JOINT,
    )
    forged_decision = _constructor_bypass(
        supplied[0],
        availability=forged_availability,
    )
    with pytest.raises(GeneratorValidationError):
        build_external_distribution_fact_set((forged_decision,))


def test_external_fact_request_revalidates_bypassed_intended_unit() -> None:
    request = _external_fact_request()
    unit_pair = request.intended_unit_pairs[0]
    forged_unit = _constructor_bypass(
        unit_pair.record,
        realized_outcome=GeneratorOutcomeKind.REGISTERED_EXCLUSION,
    )
    forged_ref = replace(
        unit_pair.ref,
        content_digest=canonical_content_digest(forged_unit),
    )
    forged_pair = RecordRefPair(forged_unit, forged_ref)

    with pytest.raises(GeneratorValidationError):
        build_external_distribution_fact_request(
            result_pairs=request.result_pairs,
            intended_unit_pairs=(forged_pair,),
            accounting_summary=request.accounting_summary,
            accounting_summary_ref=request.accounting_summary_ref,
            requested_fact_kind=request.requested_fact_kind,
            statistics_objective_ref=request.statistics_objective_ref,
            owner_unavailable_reason_ref=request.owner_unavailable_reason_ref,
        )
