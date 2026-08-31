"""Closed result-graph validation and canonical tamper rejection for B-03."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, fields, replace

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.authoring.model import ApplicabilityBinding
from carbon.generators.accounting import (
    GenerationAttemptRecord,
    PendingGenerationAttempt,
    build_generation_accounting_summary,
    build_intended_unit_accounting,
)
from carbon.generators.burgers import GeneratedFixtureArtifact
from carbon.generators.canonical import canonical_bytes, decode_canonical_bytes
from carbon.generators.errors import (
    GeneratorCanonicalDecodingError,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GeneratorFailureReason,
    GeneratorInvocationOutput,
    GeneratorInvocationOutputKind,
    GeneratorOutcomeKind,
    GeneratorRequestIdentity,
    GeneratorResult,
    GeneratorResultRecord,
    GeneratorTerminalStage,
    RecordRefPair,
    SourceMaterializationState,
    TerminalReasonFailure,
)
from carbon.generators.service import generate_fixture_case
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import SeedDomain

_HOSTILE_DEPENDENCY_SECRET = "hostile-resolved-dependency-secret"


class _HostileDependencyError(RuntimeError):
    pass


class _HostileResolvedDependency:
    def to_ref(self) -> object:
        raise _HostileDependencyError(_HOSTILE_DEPENDENCY_SECRET)


@dataclass(frozen=True)
class _GeneratedRecords:
    valid: GeneratorResultRecord
    exclusion: GeneratorResultRecord
    nonconformance: GeneratorResultRecord
    censored: GeneratorResultRecord
    support_infrastructure: GeneratorResultRecord
    accounting_infrastructure: GeneratorResultRecord


def _generate_subject(
    **fixture_options: object,
) -> tuple[object, GeneratorResultRecord]:
    fixture = make_b03_fixture(**fixture_options)
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    return fixture, output.payload.record


def _generate_result(**fixture_options: object) -> tuple[object, GeneratorResult]:
    fixture = make_b03_fixture(**fixture_options)
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    return fixture, output.payload


def _generate_record(**fixture_options: object) -> GeneratorResultRecord:
    return _generate_subject(**fixture_options)[1]


@pytest.fixture(scope="module")
def records() -> _GeneratedRecords:
    return _GeneratedRecords(
        valid=_generate_record(),
        exclusion=_generate_record(support_mode="excluded"),
        nonconformance=_generate_record(support_mode="outside"),
        censored=_generate_record(censoring_mode="censored"),
        support_infrastructure=_generate_record(support_mode="unavailable"),
        accounting_infrastructure=_generate_record(accounting_unavailable=True),
    )


def _constructor_bypass(value: object, **updates: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        field_name = field.name
        object.__setattr__(
            forged,
            field_name,
            updates.get(field_name, getattr(value, field_name)),
        )
    return forged


@pytest.mark.parametrize(
    "record_name",
    (
        "valid",
        "exclusion",
        "nonconformance",
        "censored",
        "support_infrastructure",
        "accounting_infrastructure",
    ),
)
def test_every_generated_result_has_an_exact_canonical_round_trip(
    records: _GeneratedRecords,
    record_name: str,
) -> None:
    record = getattr(records, record_name)

    decoded = decode_canonical_bytes(record.canonical_bytes(), GeneratorResultRecord)

    assert decoded.canonical_bytes() == record.canonical_bytes()
    assert decoded.to_ref() == record.to_ref()


def test_result_rejects_closed_stage_and_request_identity_tampering(
    records: _GeneratedRecords,
) -> None:
    record = records.valid
    forged_request_ref = replace(
        record.request_ref,
        content_digest="sha256:" + "f" * 64,
    )
    forged_event = replace(
        record.source_event,
        generator_ref=challenge_owner("generator", "forged_generator_echo"),
    )

    with pytest.raises(GeneratorValidationError):
        replace(record, terminal_stage=GeneratorTerminalStage.SUPPORT_AUTHORITY)
    with pytest.raises(GeneratorValidationError):
        replace(record, request_ref=forged_request_ref)
    with pytest.raises(GeneratorValidationError):
        replace(
            record,
            source_event=forged_event,
            source_event_ref=forged_event.to_ref(),
        )


def test_source_event_not_applicable_payload_reason_is_challenge_scoped(
    records: _GeneratedRecords,
) -> None:
    event = records.valid.source_event
    identity = records.valid.conformance_facts.request_identity
    valid_not_applicable = replace(
        event,
        payload_ref_binding=ApplicabilityBinding.not_applicable(
            identity.source_payload_inapplicable_reason_ref
        ),
        materialization_state=SourceMaterializationState.NO_PAYLOAD,
    )
    assert not valid_not_applicable.payload_ref_binding.is_bound

    cross_challenge_reason = challenge_owner(
        "applicability_reason",
        "cross_challenge_source_payload_reason",
        challenge_key=ChallengeKey("b03_other_challenge", "1.0"),
    )
    with pytest.raises(GeneratorValidationError) as caught:
        replace(
            event,
            payload_ref_binding=ApplicabilityBinding.not_applicable(
                cross_challenge_reason
            ),
            materialization_state=SourceMaterializationState.NO_PAYLOAD,
        )
    assert caught.value.code == "CROSS_CHALLENGE"


def test_request_identity_revalidates_role_seed_domain_and_canonical_decode(
    records: _GeneratedRecords,
) -> None:
    identity = records.valid.conformance_facts.request_identity
    assert identity.role_binding.seed_domain is SeedDomain.OFFICIAL_EVAL
    forged_role = _constructor_bypass(
        identity.role_binding,
        seed_domain=SeedDomain.OFFICIAL_TRAIN,
    )

    with pytest.raises(GeneratorValidationError):
        replace(identity, role_binding=forged_role)

    forged_identity = _constructor_bypass(identity, role_binding=forged_role)
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            forged_identity.canonical_bytes(),
            GeneratorRequestIdentity,
        )


def test_authoring_bundle_sanitizes_hostile_resolved_dependency_exceptions() -> None:
    fixture = make_b03_fixture()
    bundle = fixture.request.authoring_bundle
    dependency_ref = bundle.resolved_dependencies[0][0]

    with pytest.raises(GeneratorValidationError) as caught:
        replace(
            bundle,
            resolved_dependencies=((dependency_ref, _HostileResolvedDependency()),),
        )
    error = caught.value
    assert error.code == "STALE_BINDING"
    assert error.path == "/resolved_dependencies"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert _HOSTILE_DEPENDENCY_SECRET not in str(error) + repr(error)


@pytest.mark.parametrize(
    ("target_name", "field_name", "donor_name"),
    (
        ("valid", "case_binding", "exclusion"),
        ("exclusion", "case_binding", "valid"),
        ("valid", "constructed_case_binding", "exclusion"),
        (
            "accounting_infrastructure",
            "constructed_case_binding",
            "support_infrastructure",
        ),
    ),
)
def test_result_rejects_impossible_bound_and_not_applicable_shapes(
    records: _GeneratedRecords,
    target_name: str,
    field_name: str,
    donor_name: str,
) -> None:
    target = getattr(records, target_name)
    donor = getattr(records, donor_name)

    with pytest.raises(GeneratorValidationError):
        replace(target, **{field_name: getattr(donor, field_name)})


def test_result_rejects_wrong_terminal_reason_and_disposition_variants(
    records: _GeneratedRecords,
) -> None:
    with pytest.raises(GeneratorValidationError):
        replace(
            records.valid,
            terminal_reason_binding=records.exclusion.terminal_reason_binding,
        )
    with pytest.raises(GeneratorValidationError):
        replace(
            records.nonconformance,
            terminal_reason_binding=(
                records.support_infrastructure.terminal_reason_binding
            ),
        )
    with pytest.raises(GeneratorValidationError):
        replace(
            records.valid,
            disposition_binding=records.exclusion.disposition_binding,
        )


def test_every_terminal_reason_variant_rejects_subclasses(
    records: _GeneratedRecords,
) -> None:
    variants = (
        records.valid.terminal_reason_binding,
        records.exclusion.terminal_reason_binding,
        records.censored.terminal_reason_binding,
        records.support_infrastructure.terminal_reason_binding,
    )
    for value in variants:
        value_type = type(value)
        subclass = type(f"{value_type.__name__}Subclass", (value_type,), {})
        constructor_values = {
            field.name: getattr(value, field.name) for field in fields(value)
        }

        with pytest.raises(GeneratorValidationError):
            subclass(**constructor_values)


@pytest.mark.parametrize(
    ("object_field", "ref_field"),
    (
        ("attempt_accounting_decision", "attempt_accounting_decision_ref"),
        ("attempt_record", "attempt_record_ref"),
        ("conformance_facts", "conformance_facts_ref"),
    ),
)
def test_result_rejects_other_exact_object_ref_pairs_from_the_same_request(
    records: _GeneratedRecords,
    object_field: str,
    ref_field: str,
) -> None:
    target = records.valid
    donor = records.exclusion

    with pytest.raises(GeneratorValidationError):
        replace(
            target,
            **{
                object_field: getattr(donor, object_field),
                ref_field: getattr(donor, ref_field),
            },
        )


def test_result_and_invocation_wrappers_reject_fake_nominals_and_subclasses(
    records: _GeneratedRecords,
) -> None:
    record = records.valid
    fake_artifact_type = type(
        "GeneratedFixtureArtifact",
        (),
        {"__module__": "carbon.generators.burgers"},
    )
    fake_pending_type = type(
        "PendingGenerationAttempt",
        (),
        {"__module__": "carbon.generators.accounting"},
    )
    artifact_subclass = type(
        "ArtifactSubclass",
        (GeneratedFixtureArtifact,),
        {},
    )
    pending_subclass = type(
        "PendingSubclass",
        (PendingGenerationAttempt,),
        {},
    )
    bad_artifacts = (
        fake_artifact_type(),
        object.__new__(artifact_subclass),
    )
    bad_pending = (
        fake_pending_type(),
        object.__new__(pending_subclass),
    )

    for artifact in bad_artifacts:
        with pytest.raises(GeneratorValidationError):
            GeneratorResult(record, record.to_ref(), artifact)
    for pending in bad_pending:
        with pytest.raises(GeneratorValidationError):
            GeneratorInvocationOutput(
                GeneratorInvocationOutputKind.PENDING_SUCCESSOR,
                pending,
            )


def test_result_wrapper_reconstructs_and_deep_revalidates_record_and_artifact() -> None:
    _, result = _generate_result()
    checked = GeneratorResult(result.record, result.ref, result.artifact)

    assert checked.record is not result.record
    assert checked.artifact is not result.artifact
    assert checked.ref == result.ref

    forged_record = _constructor_bypass(
        result.record,
        terminal_stage=GeneratorTerminalStage.SUPPORT_AUTHORITY,
    )
    forged_record_ref = forged_record.to_ref()
    with pytest.raises(GeneratorValidationError):
        GeneratorResult(forged_record, forged_record_ref, result.artifact)

    forged_artifact = _constructor_bypass(
        result.artifact,
        case_ref=replace(
            result.artifact.case_ref,
            content_digest="sha256:" + "f" * 64,
        ),
    )
    with pytest.raises(GeneratorValidationError):
        GeneratorResult(result.record, result.ref, forged_artifact)

    forged_graph = _constructor_bypass(
        result.artifact.graph_origin,
        composition_audit_ref=challenge_owner(
            "origin_composition_audit",
            "alternate_composition_audit",
        ),
    )
    forged_artifact = _constructor_bypass(
        result.artifact,
        graph_origin=forged_graph,
    )
    with pytest.raises(GeneratorValidationError):
        GeneratorResult(result.record, result.ref, forged_artifact)

    first_dependency, *remaining_dependencies = result.artifact.loaded_dependencies
    forged_dependency = _constructor_bypass(
        first_dependency,
        authored_object="forged-loaded-dependency",
    )
    forged_artifact = _constructor_bypass(
        result.artifact,
        loaded_dependencies=(forged_dependency, *remaining_dependencies),
    )
    with pytest.raises(GeneratorValidationError):
        GeneratorResult(result.record, result.ref, forged_artifact)

    forged_result = _constructor_bypass(
        result,
        record=forged_record,
        ref=forged_record_ref,
    )
    with pytest.raises(GeneratorValidationError):
        GeneratorInvocationOutput.final(forged_result)


@pytest.mark.parametrize("target_name", ("valid", "censored"))
def test_attempt_record_rejects_same_request_outside_support_conformance_pair(
    records: _GeneratedRecords,
    target_name: str,
) -> None:
    target = getattr(records, target_name).attempt_record
    donor = records.nonconformance
    donor_pair = RecordRefPair(donor.conformance_facts, donor.conformance_facts_ref)
    assert donor.conformance_facts.request_ref == target.request_ref
    assert donor.conformance_facts.source_event_ref == target.source_event_ref

    with pytest.raises(GeneratorValidationError):
        replace(target, conformance_facts_pair=donor_pair)

    forged = _constructor_bypass(target, conformance_facts_pair=donor_pair)
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(forged.canonical_bytes(), GenerationAttemptRecord)


def test_accounting_summary_revalidates_complete_intended_unit_records() -> None:
    fixture, record = _generate_subject()
    decision = record.attempt_accounting_decision
    unit, _ = build_intended_unit_accounting(
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
        accounting_directive_pairs=(decision.accounting_directive_pair,),
        accounting_decision_pairs=(
            RecordRefPair(decision, record.attempt_accounting_decision_ref),
        ),
    )
    forged = _constructor_bypass(unit, link_decision_pairs=())
    forged_pair = RecordRefPair(forged, forged.to_ref())

    with pytest.raises(GeneratorValidationError):
        build_generation_accounting_summary((forged_pair,))


def test_protected_result_graph_repr_and_pickle_never_traverse_identity_fields(
    records: _GeneratedRecords,
) -> None:
    identity = records.valid.conformance_facts.request_identity
    fixture = make_b03_fixture()
    failure_terminal = records.support_infrastructure.terminal_reason_binding
    failure_reason = failure_terminal.reason
    failure_occurrence = failure_terminal.occurrence
    catalog_entry = next(
        item
        for item in identity.failure_reason_catalog
        if item.reason == failure_reason
    )
    protected_values = (
        (
            _constructor_bypass(
                records.valid.case_binding.pair,
                record="record-ref-pair-sentinel-id",
            ),
            "record-ref-pair-sentinel-id",
        ),
        (
            _constructor_bypass(
                records.valid.case_binding,
                reason_ref="record-ref-binding-sentinel-digest",
            ),
            "record-ref-binding-sentinel-digest",
        ),
        (
            _constructor_bypass(
                identity.case_construction,
                object_id="case-construction-sentinel-id",
            ),
            "case-construction-sentinel-id",
        ),
        (
            _constructor_bypass(
                identity.fixture_loading,
                origin_evidence_ref="fixture-loading-sentinel-digest",
            ),
            "fixture-loading-sentinel-digest",
        ),
        (
            _constructor_bypass(
                identity.disposition_construction,
                policy_authority_ref="disposition-construction-sentinel-id",
            ),
            "disposition-construction-sentinel-id",
        ),
        (
            _constructor_bypass(
                fixture.request.authoring_bundle,
                physical_system="authoring-bundle-sentinel-digest",
            ),
            "authoring-bundle-sentinel-digest",
        ),
        (
            _constructor_bypass(
                identity.loaded_dependencies[0],
                origin_evidence_ref="loaded-dependency-sentinel-id",
            ),
            "loaded-dependency-sentinel-id",
        ),
        (
            _constructor_bypass(
                identity.attempt_accounting_fallback,
                authority_failure_ref="attempt-fallback-sentinel-digest",
            ),
            "attempt-fallback-sentinel-digest",
        ),
        (
            _constructor_bypass(
                identity.attempt_accounting_applicability_reasons[0],
                reason_ref="named-applicability-sentinel-id",
            ),
            "named-applicability-sentinel-id",
        ),
        (
            _constructor_bypass(
                identity.conformance_fallbacks[0],
                fallback_ref="named-conformance-sentinel-digest",
            ),
            "named-conformance-sentinel-digest",
        ),
        (
            _constructor_bypass(
                identity,
                attempt_ref="request-identity-sentinel-id",
            ),
            "request-identity-sentinel-id",
        ),
        (
            _constructor_bypass(
                records.valid.source_event,
                generator_ref="source-event-sentinel-digest",
            ),
            "source-event-sentinel-digest",
        ),
        (
            _constructor_bypass(
                records.valid,
                source_provenance_refs=("result-record-sentinel-id",),
            ),
            "result-record-sentinel-id",
        ),
        (
            _constructor_bypass(
                failure_reason,
                reason_id="failure-reason-sentinel-id",
            ),
            "failure-reason-sentinel-id",
        ),
        (
            _constructor_bypass(
                failure_occurrence,
                source_event_ref="failure-occurrence-sentinel-digest",
            ),
            "failure-occurrence-sentinel-digest",
        ),
        (
            _constructor_bypass(
                catalog_entry,
                occurrence_evidence_fallback="failure-catalog-sentinel-id",
            ),
            "failure-catalog-sentinel-id",
        ),
        (
            _constructor_bypass(
                records.valid.terminal_reason_binding,
                reason_ref="terminal-na-sentinel-digest",
            ),
            "terminal-na-sentinel-digest",
        ),
        (
            _constructor_bypass(
                records.exclusion.terminal_reason_binding,
                support_decision="terminal-support-sentinel-id",
            ),
            "terminal-support-sentinel-id",
        ),
        (
            _constructor_bypass(
                records.censored.terminal_reason_binding,
                censoring_record="terminal-censoring-sentinel-digest",
            ),
            "terminal-censoring-sentinel-digest",
        ),
        (
            _constructor_bypass(
                failure_terminal,
                occurrence="terminal-failure-sentinel-id",
            ),
            "terminal-failure-sentinel-id",
        ),
    )

    for value, sentinel in protected_values:
        expected = f"{type(value).__name__}(<protected>)"
        assert repr(value) == expected
        assert str(value) == expected
        assert sentinel not in repr(value) + str(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


def test_failure_reason_rejects_taxonomy_outside_the_closed_catalog(
    records: _GeneratedRecords,
) -> None:
    record = records.accounting_infrastructure
    entry = next(
        item
        for item in record.conformance_facts.request_identity.failure_reason_catalog
        if item.reason.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        and item.reason.terminal_stage
        is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY
    )
    with pytest.raises(GeneratorValidationError) as caught:
        GeneratorFailureReason(
            challenge_key=record.challenge_key,
            reason_id="fabricated_accounting_failure",
            reason_version="1.0",
            outcome_kind=entry.reason.outcome_kind,
            terminal_stage=entry.reason.terminal_stage,
            reason_code="fabricated_failure_taxonomy",
            occurrence_evidence_category=entry.reason.occurrence_evidence_category,
        )
    assert caught.value.path == "/failure_reason"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None

    bypassed = _constructor_bypass(
        entry.reason,
        reason_id="fabricated_accounting_failure",
        reason_code="fabricated_failure_taxonomy",
    )
    with pytest.raises(GeneratorValidationError):
        bypassed.canonical_bytes()
    with pytest.raises(GeneratorValidationError):
        bypassed.to_ref()
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            canonical_bytes(bypassed),
            GeneratorFailureReason,
        )


def test_failure_occurrence_and_terminal_union_are_standalone_closed(
    records: _GeneratedRecords,
) -> None:
    accounting = records.accounting_infrastructure.terminal_reason_binding
    support = records.support_infrastructure.terminal_reason_binding
    occurrence = accounting.occurrence

    with pytest.raises(GeneratorValidationError):
        replace(
            occurrence,
            occurrence_evidence_binding=ApplicabilityBinding.not_applicable(
                challenge_owner(
                    "applicability_reason",
                    "occurrence_evidence_not_applicable",
                )
            ),
        )
    with pytest.raises(GeneratorValidationError):
        replace(
            occurrence,
            occurrence_evidence_binding=ApplicabilityBinding.bound(
                challenge_owner(
                    "audit_evidence",
                    "wrong_occurrence_evidence_kind",
                )
            ),
        )
    with pytest.raises(GeneratorValidationError):
        replace(
            occurrence,
            generation_failure_alias_binding=ApplicabilityBinding.not_applicable(
                challenge_owner(
                    "applicability_reason",
                    "mismatched_failure_alias",
                )
            ),
        )
    malformed_request_ref = _constructor_bypass(
        occurrence.request_ref,
        content_digest=1,
    )
    with pytest.raises(GeneratorValidationError):
        replace(occurrence, request_ref=malformed_request_ref)
    bypassed_occurrence = _constructor_bypass(
        occurrence,
        outcome_kind=GeneratorOutcomeKind.INVALID_CONSTRUCTION,
    )
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            canonical_bytes(bypassed_occurrence),
            type(occurrence),
        )
    with pytest.raises(GeneratorValidationError):
        TerminalReasonFailure(
            accounting.reason,
            accounting.reason_ref,
            support.occurrence,
            support.occurrence_ref,
        )
