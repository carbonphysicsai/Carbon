"""Exact pending-successor execution and predecessor finalization for B-03."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from inspect import signature

import pytest
from b03_fixtures import (
    NominalAccountingAuthority,
    NominalCensoringAuthority,
    NominalSupportAuthority,
    challenge_owner,
    make_b03_fixture,
)

from carbon.authoring.evidence import ReplacementDecisionKind
from carbon.authoring.model import ApplicabilityBinding
from carbon.generators.accounting import (
    AttemptAccountingDirective,
    AttemptAccountingDirectiveKind,
    GeneratorOutcomeCount,
    PendingGenerationAttempt,
    PendingGenerationAttemptRecord,
    SuccessorAuthorization,
    build_generation_accounting_summary,
    build_intended_unit_accounting,
    finalize_pending_accounting,
)
from carbon.generators.authorities import (
    IntendedUnitLinkDecision,
    IntendedUnitLinkRequest,
)
from carbon.generators.canonical import decode_canonical_bytes
from carbon.generators.errors import (
    GeneratorCanonicalDecodingError,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GeneratorInvocationOutput,
    GeneratorInvocationOutputKind,
    GeneratorOutcomeKind,
    GeneratorRequest,
    GeneratorResult,
    GeneratorTerminalStage,
    RecordRefPair,
)
from carbon.generators.service import (
    finalize_pending_generation_attempt,
    generate_fixture_case,
)


class _PendingSuccessorAuthority:
    def __init__(self, successor_attempt_ordinal: int = 1) -> None:
        self.calls = 0
        self.successor_attempt_ordinal = successor_attempt_ordinal
        self.authorization: SuccessorAuthorization | None = None

    def decide_attempt_accounting(self, request: object) -> AttemptAccountingDirective:
        self.calls += 1
        authorization = SuccessorAuthorization(
            challenge_key=request.challenge_key,
            predecessor_request_ref=request.request_ref,
            predecessor_source_event_ref=request.source_event_ref,
            predecessor_attempt_ref=request.request_identity.attempt_ref,
            predecessor_attempt_ordinal=request.request_identity.attempt_ordinal,
            sampling_plan_ref=request.request_identity.sampling_plan_ref,
            primary_population_ref=request.request_identity.primary_population_ref,
            selection_population_ref=request.request_identity.selection_population_ref,
            intended_slot_ref=request.request_identity.intended_slot_ref,
            intended_evidence_unit_ref=(
                request.request_identity.intended_evidence_unit_ref
            ),
            registered_policy_ref=request.replacement_policy.payload.policy_ref,
            replacement_trigger=request.replacement_trigger_binding.value,
            policy_decision_kind=ReplacementDecisionKind.REQUIRED_BY_POLICY,
            replacement_accounting_evidence_ref=challenge_owner(
                "replacement_accounting",
                "pending_successor_authorization",
            ),
            successor_attempt_ref=challenge_owner(
                "protected_attempt_commitment",
                f"fixture_attempt_{self.successor_attempt_ordinal}",
            ),
            successor_attempt_ordinal=self.successor_attempt_ordinal,
            replacement_lineage_ref=challenge_owner(
                "protected_replacement_lineage",
                (
                    f"fixture_attempt_{request.request_identity.attempt_ordinal}"
                    f"_to_{self.successor_attempt_ordinal}"
                ),
            ),
        )
        self.authorization = authorization
        return AttemptAccountingDirective(
            challenge_key=request.challenge_key,
            request=request,
            directive_kind=AttemptAccountingDirectiveKind.PENDING_SUCCESSOR,
            provisional_outcome=request.provisional_outcome,
            provisional_stage=request.provisional_stage,
            final_outcome=None,
            final_stage=None,
            outcome_replacement_binding=ApplicabilityBinding.not_applicable(
                request.outcome_replacement_inapplicable_reason_ref
            ),
            successor_authorization_binding=ApplicabilityBinding.bound(authorization),
            denominator_effect_binding=ApplicabilityBinding.bound(
                request.replacement_policy.payload.denominator_effect_ref
            ),
            accounting_authority_failure_ref=None,
        )


class _IntSubclass(int):
    pass


@dataclass(frozen=True)
class _PendingScenario:
    predecessor_request: GeneratorRequest
    pending: PendingGenerationAttempt
    authorization: SuccessorAuthorization
    successor_request: GeneratorRequest
    successor_output: GeneratorInvocationOutput
    final_result: GeneratorResult


def _successor_request(
    predecessor: GeneratorRequest,
    pending: PendingGenerationAttempt,
    authorization: SuccessorAuthorization,
    *,
    replay_ref: object,
) -> GeneratorRequest:
    link_request = IntendedUnitLinkRequest(
        challenge_key=predecessor.challenge_key,
        sampling_plan_ref=predecessor.authoring_bundle.sampling_plan_ref,
        selection_population_ref=predecessor.authoring_bundle.selection_population_ref,
        role_binding=predecessor.role_binding,
        replay_ref=replay_ref,
        intended_slot_ref=predecessor.intended_slot_ref,
        intended_evidence_unit_ref=predecessor.intended_evidence_unit_ref,
        attempt_ref=authorization.successor_attempt_ref,
    )
    link_decision = IntendedUnitLinkDecision(
        challenge_key=predecessor.challenge_key,
        request=link_request,
        link_evidence_ref=challenge_owner(
            "authority_evidence",
            "fixture_successor_intended_unit_link",
        ),
    )
    return replace(
        predecessor,
        replay_ref=replay_ref,
        intended_unit_link_decision=link_decision,
        intended_unit_link_decision_ref=link_decision.to_ref(),
        attempt_ref=authorization.successor_attempt_ref,
        attempt_ordinal=authorization.successor_attempt_ordinal,
        current_attempt_predecessor_binding=RecordRefPair(
            pending.record,
            pending.ref,
        ),
        current_attempt_lineage_binding=authorization.replacement_lineage_ref,
    )


@pytest.fixture(scope="module")
def scenario() -> _PendingScenario:
    fixture = make_b03_fixture(support_mode="outside")
    pending_authority = _PendingSuccessorAuthority()
    predecessor_output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=pending_authority,
    )
    assert predecessor_output.kind is GeneratorInvocationOutputKind.PENDING_SUCCESSOR
    pending = predecessor_output.payload
    authorization = pending_authority.authorization
    assert type(authorization) is SuccessorAuthorization

    successor_request = _successor_request(
        fixture.request,
        pending,
        authorization,
        replay_ref=fixture.fixture_authority.reserve_replay(),
    )
    successor_output = generate_fixture_case(
        successor_request,
        fixture_authority=fixture.fixture_authority,
        support_authority=NominalSupportAuthority(
            fixture.bundle,
            fixture.prospective_exclusion_ref,
            "within",
        ),
        censoring_authority=NominalCensoringAuthority(),
        accounting_authority=NominalAccountingAuthority(),
    )
    final_result = finalize_pending_generation_attempt(
        predecessor_request=fixture.request,
        pending=pending,
        successor_request=successor_request,
        successor_output=successor_output,
    )
    return _PendingScenario(
        predecessor_request=fixture.request,
        pending=pending,
        authorization=authorization,
        successor_request=successor_request,
        successor_output=successor_output,
        final_result=final_result,
    )


def _constructor_bypass(value: object, **updates: object) -> object:
    forged = object.__new__(type(value))
    for field_name in value.__dataclass_fields__:
        object.__setattr__(
            forged,
            field_name,
            updates.get(field_name, getattr(value, field_name)),
        )
    return forged


def _complete_accounting_values(scenario: _PendingScenario) -> tuple[object, ...]:
    predecessor_record = scenario.final_result.record
    successor_record = scenario.successor_output.payload.record
    predecessor_decision = predecessor_record.attempt_accounting_decision
    successor_decision = successor_record.attempt_accounting_decision
    unit, unit_ref = build_intended_unit_accounting(
        link_decision_pairs=(
            RecordRefPair(
                scenario.predecessor_request.intended_unit_link_decision,
                scenario.predecessor_request.intended_unit_link_decision_ref,
            ),
            RecordRefPair(
                scenario.successor_request.intended_unit_link_decision,
                scenario.successor_request.intended_unit_link_decision_ref,
            ),
        ),
        attempt_record_pairs=(
            RecordRefPair(
                predecessor_record.attempt_record,
                predecessor_record.attempt_record_ref,
            ),
            RecordRefPair(
                successor_record.attempt_record,
                successor_record.attempt_record_ref,
            ),
        ),
        pending_attempt_pairs=(
            RecordRefPair(scenario.pending.record, scenario.pending.ref),
        ),
        accounting_directive_pairs=(
            predecessor_decision.accounting_directive_pair,
            successor_decision.accounting_directive_pair,
        ),
        accounting_decision_pairs=(
            RecordRefPair(
                predecessor_decision,
                predecessor_record.attempt_accounting_decision_ref,
            ),
            RecordRefPair(
                successor_decision,
                successor_record.attempt_accounting_decision_ref,
            ),
        ),
    )
    summary, _ = build_generation_accounting_summary((RecordRefPair(unit, unit_ref),))
    evidence = predecessor_decision.successor_execution_binding.value
    return (
        scenario.pending.record.accounting_directive_pair.record.request,
        scenario.authorization,
        scenario.pending.record.accounting_directive_pair.record,
        scenario.pending.record,
        scenario.pending,
        evidence,
        predecessor_decision,
        predecessor_record.attempt_record,
        GeneratorOutcomeCount(GeneratorOutcomeKind.VALID_GENERATED, 1),
        unit,
        summary,
    )


def test_outside_support_pending_successor_executes_once_and_finalizes_predecessor(
    scenario: _PendingScenario,
) -> None:
    successor_result = scenario.successor_output.payload
    predecessor = scenario.final_result.record
    decision = predecessor.attempt_accounting_decision
    evidence = decision.successor_execution_binding.value

    assert successor_result.record.outcome_kind is GeneratorOutcomeKind.VALID_GENERATED
    assert predecessor.outcome_kind is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE
    assert (
        predecessor.attempt_record.pending_attempt_binding.value == scenario.pending.ref
    )
    assert decision.successor_execution_binding.is_bound
    assert evidence.authorization == scenario.authorization
    assert (
        evidence.successor_request_pair.record == scenario.successor_request.identity()
    )
    assert evidence.successor_output_pair.record == successor_result.record
    assert evidence.successor_output_pair.ref == successor_result.ref

    accounting_values = _complete_accounting_values(scenario)
    unit, summary = accounting_values[-2:]
    attempt_counts = {
        item.outcome_kind: item.count for item in summary.attempt_outcome_counts
    }
    realized_counts = {
        item.outcome_kind: item.count for item in summary.realized_outcome_counts
    }
    assert summary.attempt_count == 2
    assert summary.intended_unit_count == 1
    assert attempt_counts[GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE] == 1
    assert attempt_counts[GeneratorOutcomeKind.VALID_GENERATED] == 1
    assert realized_counts[GeneratorOutcomeKind.VALID_GENERATED] == 1
    assert unit.realized_outcome is GeneratorOutcomeKind.VALID_GENERATED
    assert summary.realized_valid_case_refs == (unit.realized_case_ref,)


def test_case_bearing_pending_wrapper_binds_artifact_to_conformance_facts() -> None:
    fixture = make_b03_fixture(censoring_mode="censored")
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=_PendingSuccessorAuthority(),
    )
    assert output.kind is GeneratorInvocationOutputKind.PENDING_SUCCESSOR
    pending = output.payload
    assert pending.artifact is not None
    forged_graph = _constructor_bypass(
        pending.artifact.graph_origin,
        composition_audit_ref=challenge_owner(
            "origin_composition_audit",
            "pending_alternate_composition_audit",
        ),
    )
    forged_artifact = _constructor_bypass(
        pending.artifact,
        graph_origin=forged_graph,
    )

    with pytest.raises(GeneratorValidationError):
        replace(pending, artifact=forged_artifact)


def test_every_accounting_dataclass_owns_serialization_rejection(
    scenario: _PendingScenario,
) -> None:
    for value in _complete_accounting_values(scenario):
        value_type = type(value)
        field_name = fields(value)[0].name
        sentinel = f"{value_type.__name__}-serialization-sentinel"
        forged = _constructor_bypass(value, **{field_name: sentinel})

        assert "__reduce__" in value_type.__dict__
        assert "__reduce_ex__" in value_type.__dict__
        assert repr(forged) == f"{value_type.__name__}(<protected>)"
        assert sentinel not in repr(forged) + str(forged)
        with pytest.raises(TypeError):
            forged.__reduce__()
        with pytest.raises(TypeError):
            forged.__reduce_ex__(pickle.HIGHEST_PROTOCOL)
        with pytest.raises(TypeError):
            pickle.dumps(forged)


def test_every_accounting_dataclass_rejects_subclasses(
    scenario: _PendingScenario,
) -> None:
    for value in _complete_accounting_values(scenario):
        value_type = type(value)
        subclass = type(f"{value_type.__name__}Subclass", (value_type,), {})
        constructor_values = {
            field.name: getattr(value, field.name) for field in fields(value)
        }

        with pytest.raises(GeneratorValidationError):
            subclass(**constructor_values)


def test_public_uint64_constructor_boundaries(
    scenario: _PendingScenario,
) -> None:
    maximum = (1 << 64) - 1
    invalid_values = (
        maximum + 1,
        True,
        _IntSubclass(0),
        0.0,
        "0",
        Decimal(0),
    )

    for value in (0, maximum):
        assert (
            GeneratorOutcomeCount(
                GeneratorOutcomeKind.VALID_GENERATED,
                value,
            ).count
            == value
        )
        assert (
            replace(
                scenario.predecessor_request,
                attempt_ordinal=value,
            ).attempt_ordinal
            == value
        )
        assert (
            replace(
                scenario.final_result.record.attempt_record,
                attempt_ordinal=value,
            ).attempt_ordinal
            == value
        )

    for value in invalid_values:
        with pytest.raises(GeneratorValidationError):
            GeneratorOutcomeCount(GeneratorOutcomeKind.VALID_GENERATED, value)
        with pytest.raises(GeneratorValidationError):
            replace(scenario.predecessor_request, attempt_ordinal=value)
        with pytest.raises(GeneratorValidationError):
            replace(
                scenario.final_result.record.attempt_record,
                attempt_ordinal=value,
            )

    authorization = scenario.authorization
    assert (
        replace(
            authorization,
            predecessor_attempt_ordinal=0,
            successor_attempt_ordinal=1,
        ).predecessor_attempt_ordinal
        == 0
    )
    assert (
        replace(
            authorization,
            predecessor_attempt_ordinal=0,
            successor_attempt_ordinal=maximum,
        ).successor_attempt_ordinal
        == maximum
    )
    with pytest.raises(GeneratorValidationError):
        replace(
            authorization,
            predecessor_attempt_ordinal=maximum,
            successor_attempt_ordinal=maximum,
        )
    with pytest.raises(GeneratorValidationError):
        replace(
            authorization,
            predecessor_attempt_ordinal=0,
            successor_attempt_ordinal=0,
        )
    for value in invalid_values:
        with pytest.raises(GeneratorValidationError):
            replace(authorization, predecessor_attempt_ordinal=value)
        with pytest.raises(GeneratorValidationError):
            replace(authorization, successor_attempt_ordinal=value)


def test_pending_finalizer_rejects_wrong_pending_and_successor_identity_echoes(
    scenario: _PendingScenario,
) -> None:
    successor = scenario.successor_request
    wrong_pending_ref = replace(
        scenario.pending.ref,
        content_digest="sha256:" + "f" * 64,
    )
    wrong_pending_pair = _constructor_bypass(
        successor.current_attempt_predecessor_binding,
        ref=wrong_pending_ref,
    )
    wrong_generator = replace(
        successor.generator,
        generator_id="wrong_successor_continuity",
    )
    tampered_requests = (
        replace(successor, current_attempt_predecessor_binding=wrong_pending_pair),
        replace(
            successor,
            attempt_ref=challenge_owner(
                "protected_attempt_commitment",
                "wrong_successor_attempt",
            ),
        ),
        replace(successor, attempt_ordinal=2),
        replace(
            successor,
            current_attempt_lineage_binding=challenge_owner(
                "protected_replacement_lineage",
                "wrong_successor_lineage",
            ),
        ),
        replace(
            successor,
            generator=wrong_generator,
            generator_ref=wrong_generator.to_ref(),
        ),
    )

    for tampered_request in tampered_requests:
        with pytest.raises(GeneratorValidationError):
            finalize_pending_generation_attempt(
                predecessor_request=scenario.predecessor_request,
                pending=scenario.pending,
                successor_request=tampered_request,
                successor_output=scenario.successor_output,
            )


def test_pending_finalizer_rejects_wrong_successor_output_pair(
    scenario: _PendingScenario,
) -> None:
    wrong_output = GeneratorInvocationOutput.pending_successor(scenario.pending)

    with pytest.raises(GeneratorValidationError):
        finalize_pending_generation_attempt(
            predecessor_request=scenario.predecessor_request,
            pending=scenario.pending,
            successor_request=scenario.successor_request,
            successor_output=wrong_output,
        )


def test_pending_finalizer_revalidates_constructor_bypassed_output_tag_payload(
    scenario: _PendingScenario,
) -> None:
    forged_output = _constructor_bypass(
        scenario.successor_output,
        kind=GeneratorInvocationOutputKind.PENDING_SUCCESSOR,
    )

    with pytest.raises(GeneratorValidationError):
        finalize_pending_generation_attempt(
            predecessor_request=scenario.predecessor_request,
            pending=scenario.pending,
            successor_request=scenario.successor_request,
            successor_output=forged_output,
        )


def test_pending_output_rejects_constructor_bypassed_stale_ref(
    scenario: _PendingScenario,
) -> None:
    checked = replace(scenario.pending)
    assert checked.record is not scenario.pending.record
    assert checked.ref == scenario.pending.ref
    stale_ref = replace(
        scenario.pending.ref,
        content_digest="sha256:" + "f" * 64,
    )
    forged = _constructor_bypass(scenario.pending, ref=stale_ref)

    with pytest.raises(GeneratorValidationError):
        GeneratorInvocationOutput.pending_successor(forged)
    with pytest.raises(GeneratorValidationError):
        finalize_pending_accounting(
            predecessor_request=scenario.predecessor_request,
            pending=forged,
            successor_request=scenario.successor_request,
            successor_output=scenario.successor_output.payload,
        )


def test_pending_wrapper_rejects_nested_stale_accounting_directive_ref(
    scenario: _PendingScenario,
) -> None:
    directive_pair = scenario.pending.record.accounting_directive_pair
    stale_directive_ref = replace(
        directive_pair.ref,
        content_digest="sha256:" + "e" * 64,
    )
    stale_directive_pair = _constructor_bypass(
        directive_pair,
        ref=stale_directive_ref,
    )
    forged_record = _constructor_bypass(
        scenario.pending.record,
        accounting_directive_pair=stale_directive_pair,
    )
    forged_pending = _constructor_bypass(
        scenario.pending,
        record=forged_record,
        ref=forged_record.to_ref(),
    )

    with pytest.raises(GeneratorValidationError):
        replace(forged_pending)
    with pytest.raises(GeneratorValidationError):
        GeneratorInvocationOutput.pending_successor(forged_pending)


def test_successor_evidence_independently_revalidates_output_record_pair(
    scenario: _PendingScenario,
) -> None:
    evidence = (
        scenario.final_result.record.attempt_accounting_decision.successor_execution_binding.value
    )
    checked = replace(evidence)
    assert (
        checked.successor_request_pair.record
        is not evidence.successor_request_pair.record
    )
    assert (
        checked.successor_output_pair.record
        is not evidence.successor_output_pair.record
    )

    output_record = scenario.successor_output.payload.record
    forged_record = _constructor_bypass(
        output_record,
        terminal_stage=GeneratorTerminalStage.SUPPORT_AUTHORITY,
    )
    forged_pair = RecordRefPair(forged_record, forged_record.to_ref())
    with pytest.raises(GeneratorValidationError):
        replace(evidence, successor_output_pair=forged_pair)


def test_exact_second_pending_is_accepted_but_cross_hop_output_rejects() -> None:
    fixture = make_b03_fixture(support_mode="outside")
    first_authority = _PendingSuccessorAuthority(1)
    first_output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=first_authority,
    )
    first_pending = first_output.payload
    first_authorization = first_authority.authorization
    assert type(first_pending) is PendingGenerationAttempt
    assert type(first_authorization) is SuccessorAuthorization
    first_successor = _successor_request(
        fixture.request,
        first_pending,
        first_authorization,
        replay_ref=fixture.fixture_authority.reserve_replay(),
    )

    second_authority = _PendingSuccessorAuthority(2)
    second_output = generate_fixture_case(
        first_successor,
        fixture_authority=fixture.fixture_authority,
        support_authority=NominalSupportAuthority(
            fixture.bundle,
            fixture.prospective_exclusion_ref,
            "outside",
        ),
        censoring_authority=NominalCensoringAuthority(),
        accounting_authority=second_authority,
    )
    second_pending = second_output.payload
    second_authorization = second_authority.authorization
    assert type(second_pending) is PendingGenerationAttempt
    assert type(second_authorization) is SuccessorAuthorization

    finalized_first = finalize_pending_generation_attempt(
        predecessor_request=fixture.request,
        pending=first_pending,
        successor_request=first_successor,
        successor_output=second_output,
    )
    evidence = (
        finalized_first.record.attempt_accounting_decision.successor_execution_binding.value
    )
    assert evidence.successor_output_pair.record == second_pending.record
    assert evidence.successor_output_pair.ref == second_pending.ref

    second_successor = _successor_request(
        first_successor,
        second_pending,
        second_authorization,
        replay_ref=fixture.fixture_authority.reserve_replay(),
    )
    with pytest.raises(GeneratorValidationError):
        finalize_pending_generation_attempt(
            predecessor_request=first_successor,
            pending=second_pending,
            successor_request=second_successor,
            successor_output=second_output,
        )


def test_pending_record_rejects_mismatched_complete_conformance_pair(
    scenario: _PendingScenario,
) -> None:
    fixture = make_b03_fixture()
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    valid_record = output.payload.record
    donor_pair = RecordRefPair(
        valid_record.conformance_facts,
        valid_record.conformance_facts_ref,
    )
    pending_record = scenario.pending.record
    assert donor_pair.record.request_ref == pending_record.request_ref
    assert donor_pair.record.source_event_ref == pending_record.source_event_pair.ref

    with pytest.raises(GeneratorValidationError):
        replace(pending_record, conformance_facts_pair=donor_pair)

    forged = _constructor_bypass(
        pending_record,
        conformance_facts_pair=donor_pair,
    )
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            forged.canonical_bytes(),
            PendingGenerationAttemptRecord,
        )


def test_pending_finalizers_accept_no_caller_execution_boolean() -> None:
    for finalizer in (
        finalize_pending_accounting,
        finalize_pending_generation_attempt,
    ):
        assert "executed" not in signature(finalizer).parameters
