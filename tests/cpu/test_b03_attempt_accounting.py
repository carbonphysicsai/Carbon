"""Focused B-03 attempt and intended-unit accounting tests."""

from __future__ import annotations

from dataclasses import fields, replace
from inspect import signature

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.generators import canonical
from carbon.generators.accounting import (
    AttemptAccountingDecision,
    AttemptAccountingDirective,
    AttemptAccountingDirectiveKind,
    AttemptAccountingRequest,
    GenerationAccountingSummary,
    GenerationAttemptRecord,
    GeneratorOutcomeCount,
    IntendedUnitAccounting,
    PendingGenerationAttemptRecord,
    SuccessorAuthorization,
    SuccessorExecutionEvidence,
    _derived_counts,
    build_generation_accounting_summary,
    build_intended_unit_accounting,
    finalize_pending_accounting,
)
from carbon.generators.errors import GeneratorInputCode, GeneratorValidationError
from carbon.generators.model import GeneratorOutcomeKind, RecordRefPair
from carbon.generators.service import generate_fixture_case


def test_accounting_directive_and_outcome_orders_are_closed() -> None:
    assert tuple(AttemptAccountingDirectiveKind) == (
        AttemptAccountingDirectiveKind.FINAL,
        AttemptAccountingDirectiveKind.PENDING_SUCCESSOR,
        AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE,
    )
    assert tuple(GeneratorOutcomeKind) == (
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.REGISTERED_EXCLUSION,
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorOutcomeKind.CENSORED_CASE,
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
    )


def test_outcome_count_is_exact_uint64_and_nested_round_trips() -> None:
    value = GeneratorOutcomeCount(GeneratorOutcomeKind.CENSORED_CASE, 3)
    encoded = canonical._nested_to_canonical(value)

    assert canonical._nested_from_canonical(encoded, GeneratorOutcomeCount) == value
    assert repr(value) == "GeneratorOutcomeCount(<protected>)"
    with pytest.raises(GeneratorValidationError) as caught:
        GeneratorOutcomeCount(GeneratorOutcomeKind.VALID_GENERATED, True)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    with pytest.raises(GeneratorValidationError):
        GeneratorOutcomeCount(GeneratorOutcomeKind.CENSORED_CASE, -1)


def test_derived_counts_have_all_six_rows_in_declaration_order() -> None:
    counts = _derived_counts(
        (
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
            GeneratorOutcomeKind.VALID_GENERATED,
        )
    )

    assert tuple(item.outcome_kind for item in counts) == tuple(GeneratorOutcomeKind)
    assert tuple(item.count for item in counts) == (2, 0, 0, 0, 0, 1)


def test_accounting_canonical_schemas_cover_literal_dataclass_fields() -> None:
    top_level = (
        AttemptAccountingDirective,
        AttemptAccountingDecision,
        PendingGenerationAttemptRecord,
        GenerationAttemptRecord,
        IntendedUnitAccounting,
        GenerationAccountingSummary,
    )
    nested = (
        AttemptAccountingRequest,
        SuccessorAuthorization,
        SuccessorExecutionEvidence,
        GeneratorOutcomeCount,
    )
    for record_type in top_level:
        schema = canonical._TOP_SCHEMAS_BY_TYPE[record_type]
        assert tuple(item.name for item in fields(record_type)) == tuple(
            name for name, _ in schema.fields
        )
    for record_type in nested:
        schema = canonical._NESTED_SCHEMAS_BY_TYPE[record_type]
        assert tuple(item.name for item in fields(record_type)) == tuple(
            name for name, _ in schema.fields
        )


def test_builders_accept_no_caller_counts_or_execution_booleans() -> None:
    summary_parameters = signature(build_generation_accounting_summary).parameters
    unit_parameters = signature(build_intended_unit_accounting).parameters
    finalizer_parameters = signature(finalize_pending_accounting).parameters

    assert tuple(summary_parameters) == ("intended_unit_pairs",)
    assert not {
        "attempt_count",
        "intended_unit_count",
        "attempt_outcome_counts",
        "realized_outcome_counts",
    } & set(summary_parameters)
    assert not {"executed", "retry_count", "attempt_count"} & set(unit_parameters)
    assert tuple(finalizer_parameters) == (
        "predecessor_request",
        "pending",
        "successor_request",
        "successor_output",
    )
    assert "executed" not in finalizer_parameters


@pytest.mark.parametrize("mutation", ("authority", "replay"))
def test_intended_unit_accounting_requires_exact_admitted_link_decision(
    mutation: str,
) -> None:
    fixture = make_b03_fixture()
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    record = output.payload.record
    accounting_decision = record.attempt_accounting_decision
    link_decision = fixture.request.intended_unit_link_decision
    if mutation == "authority":
        substituted = replace(
            link_decision,
            link_evidence_ref=challenge_owner(
                "authority_evidence",
                "substituted_intended_unit_link_authority",
            ),
        )
    else:
        substituted_request = replace(
            link_decision.request,
            replay_ref=replace(
                link_decision.request.replay_ref,
                commitment_digest="sha256:" + "7" * 64,
            ),
        )
        substituted = replace(link_decision, request=substituted_request)

    with pytest.raises(GeneratorValidationError) as caught:
        build_intended_unit_accounting(
            link_decision_pairs=(RecordRefPair(substituted, substituted.to_ref()),),
            attempt_record_pairs=(
                RecordRefPair(record.attempt_record, record.attempt_record_ref),
            ),
            pending_attempt_pairs=(),
            accounting_directive_pairs=(accounting_decision.accounting_directive_pair,),
            accounting_decision_pairs=(
                RecordRefPair(
                    accounting_decision,
                    record.attempt_accounting_decision_ref,
                ),
            ),
        )

    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value
    assert caught.value.path == "/link_decision_pairs/0"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
