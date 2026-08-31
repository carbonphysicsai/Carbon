"""Closed six-outcome and authority-call matrix for B-03 generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from b03_fixtures import B03Fixture, challenge_owner, make_b03_fixture

from carbon.authoring.evidence import GenerationFailurePayload
from carbon.authoring.model import ApplicabilityBinding, CaseState
from carbon.generators import authorities as generator_authorities
from carbon.generators import service
from carbon.generators.accounting import AttemptAccountingDirectiveKind
from carbon.generators.authorities import (
    CensoringVerdict,
    CensoringVerdictKind,
    PopulationAssessmentRole,
    PopulationSupportDecisionKind,
    SupportExclusionDecisionKind,
)
from carbon.generators.errors import GeneratorInputCode, GeneratorValidationError
from carbon.generators.model import (
    GeneratorInvocationOutputKind,
    GeneratorOutcomeKind,
    GeneratorTerminalStage,
    SourceMaterializationState,
    TerminalReasonFailure,
)
from carbon.registry.model import ChallengeKey


def _invalid_case_construction(*args, **kwargs):
    del args, kwargs
    raise ValueError("fixture-selected malformed construction")


def _semantic_boundary_failure(*args, **kwargs):
    del args, kwargs
    raise ValueError("fixture-selected semantic failure")


def _infrastructure_boundary_failure(*args, **kwargs):
    del args, kwargs
    raise RuntimeError("fixture-selected infrastructure failure")


def _constructor_bypass(value: object, **updates: object) -> object:
    forged = object.__new__(type(value))
    for field_name in value.__dataclass_fields__:
        object.__setattr__(
            forged,
            field_name,
            updates.get(field_name, getattr(value, field_name)),
        )
    return forged


_MATRIX: tuple[
    tuple[
        str,
        Callable[[], B03Fixture],
        GeneratorOutcomeKind,
        GeneratorTerminalStage,
        tuple[int, int, int],
        bool,
    ],
    ...,
] = (
    (
        "valid",
        make_b03_fixture,
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorTerminalStage.CENSORING_COMPLETION,
        (1, 1, 1),
        False,
    ),
    (
        "registered_exclusion",
        lambda: make_b03_fixture(support_mode="excluded"),
        GeneratorOutcomeKind.REGISTERED_EXCLUSION,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        (1, 0, 1),
        False,
    ),
    (
        "generator_nonconformance",
        lambda: make_b03_fixture(support_mode="outside"),
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        (1, 0, 1),
        False,
    ),
    (
        "invalid_construction",
        make_b03_fixture,
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        (1, 0, 1),
        True,
    ),
    (
        "censored_case",
        lambda: make_b03_fixture(censoring_mode="censored"),
        GeneratorOutcomeKind.CENSORED_CASE,
        GeneratorTerminalStage.CENSORING_COMPLETION,
        (1, 1, 1),
        False,
    ),
    (
        "infrastructure_failure",
        lambda: make_b03_fixture(support_mode="unavailable"),
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        (1, 0, 1),
        False,
    ),
)


_FAILURE_STAGE_MATRIX = (
    (
        "materialization_nonconformance",
        "materialization_semantic",
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_sampler_contract_violation",
        SourceMaterializationState.NO_PAYLOAD,
    ),
    (
        "support_nonconformance",
        "support_outside",
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_outside_registered_support",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "construction_compatibility_invalid",
        "construction_semantic",
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY,
        "b03_construction_compatibility_failed",
        SourceMaterializationState.NOT_ATTEMPTED,
    ),
    (
        "case_construction_invalid",
        "case_semantic",
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_failed",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "graph_validation_invalid",
        "graph_semantic",
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_authoring_graph_invalid",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "context_acquisition_infrastructure",
        "context_infrastructure",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CONTEXT_ACQUISITION,
        "b03_context_acquisition_unavailable",
        SourceMaterializationState.NO_PAYLOAD,
    ),
    (
        "derivation_infrastructure",
        "derivation_infrastructure",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.DERIVATION,
        "b03_seed_derivation_unavailable",
        SourceMaterializationState.NO_PAYLOAD,
    ),
    (
        "materialization_infrastructure",
        "materialization_infrastructure",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_materialization_infrastructure_failure",
        SourceMaterializationState.NO_PAYLOAD,
    ),
    (
        "support_infrastructure",
        "support_unavailable",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_support_authority_unavailable",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "case_construction_infrastructure",
        "case_infrastructure",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_infrastructure_failure",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "censoring_infrastructure",
        "censor_unavailable",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CENSORING_AUTHORITY,
        "b03_censoring_authority_unavailable",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "accounting_infrastructure",
        "accounting_unavailable",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
        "b03_attempt_accounting_authority_unavailable",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
    (
        "graph_validation_infrastructure",
        "graph_infrastructure",
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_graph_validation_infrastructure_failure",
        SourceMaterializationState.PAYLOAD_AVAILABLE,
    ),
)


def _failure_fixture(fault: str) -> B03Fixture:
    if fault == "support_outside":
        return make_b03_fixture(support_mode="outside")
    if fault == "support_unavailable":
        return make_b03_fixture(support_mode="unavailable")
    if fault == "censor_unavailable":
        return make_b03_fixture(censoring_mode="unavailable")
    if fault == "accounting_unavailable":
        return make_b03_fixture(accounting_unavailable=True)
    return make_b03_fixture()


def _install_failure_fault(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    if fault == "construction_semantic":
        monkeypatch.setattr(
            service,
            "validate_candidate_against_physical",
            _semantic_boundary_failure,
        )
    elif fault == "context_infrastructure":
        monkeypatch.setattr(
            generator_authorities,
            "acquire_fixture_official_context",
            _infrastructure_boundary_failure,
        )
    elif fault == "derivation_infrastructure":
        monkeypatch.setattr(
            generator_authorities.FixtureGenerationGrant,
            "derive_once",
            _infrastructure_boundary_failure,
        )
    elif fault == "materialization_semantic":
        monkeypatch.setattr(
            service,
            "_materialize_burgers_fixture_payload",
            _semantic_boundary_failure,
        )
    elif fault == "materialization_infrastructure":
        monkeypatch.setattr(
            service,
            "_materialize_burgers_fixture_payload",
            _infrastructure_boundary_failure,
        )
    elif fault == "case_semantic":
        monkeypatch.setattr(
            service,
            "build_generated_case",
            _semantic_boundary_failure,
        )
    elif fault == "case_infrastructure":
        monkeypatch.setattr(
            service,
            "build_generated_case",
            _infrastructure_boundary_failure,
        )
    elif fault == "graph_semantic":
        monkeypatch.setattr(
            service,
            "build_generated_artifact",
            _semantic_boundary_failure,
        )
    elif fault == "graph_infrastructure":
        monkeypatch.setattr(
            service,
            "build_generated_artifact",
            _infrastructure_boundary_failure,
        )


@pytest.mark.parametrize(
    (
        "case_id",
        "fixture_factory",
        "expected_outcome",
        "expected_stage",
        "expected_calls",
        "force_invalid_case",
    ),
    _MATRIX,
    ids=tuple(row[0] for row in _MATRIX),
)
def test_closed_outcome_matrix_is_final_visible_and_never_retries(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    fixture_factory: Callable[[], B03Fixture],
    expected_outcome: GeneratorOutcomeKind,
    expected_stage: GeneratorTerminalStage,
    expected_calls: tuple[int, int, int],
    force_invalid_case: bool,
) -> None:
    del case_id
    fixture = fixture_factory()
    if force_invalid_case:
        monkeypatch.setattr(
            service,
            "build_generated_case",
            _invalid_case_construction,
        )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    assert output.kind is GeneratorInvocationOutputKind.FINAL
    record = output.payload.record
    assert record.outcome_kind is expected_outcome
    assert record.terminal_stage is expected_stage
    assert record.attempt_record.outcome_kind is expected_outcome
    assert record.attempt_record.terminal_stage is expected_stage
    assert record.attempt_record.attempt_ref == fixture.request.attempt_ref
    assert record.attempt_record.attempt_ordinal == 0
    case_expected = expected_outcome in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.CENSORED_CASE,
    }
    assert record.case_binding.is_bound is case_expected
    assert record.constructed_case_binding.is_bound is case_expected
    assert (output.payload.artifact is not None) is case_expected
    disposition_expected = expected_outcome in {
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.REGISTERED_EXCLUSION,
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorOutcomeKind.CENSORED_CASE,
    }
    assert record.disposition_binding.is_bound is disposition_expected
    expected_states = {
        GeneratorOutcomeKind.VALID_GENERATED: CaseState.VALID,
        GeneratorOutcomeKind.REGISTERED_EXCLUSION: CaseState.EXCLUDED,
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE: CaseState.GENERATION_FAILURE,
        GeneratorOutcomeKind.CENSORED_CASE: CaseState.CENSORED,
    }
    if disposition_expected:
        assert (
            record.disposition_binding.pair.record.case_state
            is expected_states[expected_outcome]
        )
    assert (
        record.attempt_accounting_decision.accounting_directive_pair.record.directive_kind
        is AttemptAccountingDirectiveKind.FINAL
    )
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == expected_calls


@pytest.mark.parametrize(
    ("authority_name", "raw_authority"),
    (
        ("fixture_authority", True),
        ("fixture_authority", lambda request: request),
        ("support_authority", False),
        ("support_authority", lambda request: request),
        ("censoring_authority", True),
        ("censoring_authority", lambda request: request),
        ("accounting_authority", False),
        ("accounting_authority", lambda request: request),
    ),
)
def test_raw_callbacks_and_booleans_are_not_authority_interfaces(
    authority_name: str,
    raw_authority: object,
) -> None:
    fixture = make_b03_fixture()
    authorities = {
        "fixture_authority": fixture.fixture_authority,
        "support_authority": fixture.support_authority,
        "censoring_authority": fixture.censoring_authority,
        "accounting_authority": fixture.accounting_authority,
    }
    authorities[authority_name] = raw_authority

    with pytest.raises(GeneratorValidationError) as caught:
        service.generate_fixture_case(fixture.request, **authorities)

    assert caught.value.code == GeneratorInputCode.AUTHORITY_INTERFACE_INVALID.value
    assert caught.value.path == f"/{authority_name}"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == (0, 0, 0)
    fixture.fixture_authority.require_available(fixture.request.replay_ref)


def test_failure_stage_matrix_covers_the_exact_admitted_catalog() -> None:
    fixture = make_b03_fixture()
    expected_rows = tuple(
        (outcome, stage, reason_id)
        for _, _, outcome, stage, reason_id, _ in _FAILURE_STAGE_MATRIX
    )
    admitted_rows = tuple(
        (
            entry.reason.outcome_kind,
            entry.reason.terminal_stage,
            entry.reason.reason_id,
        )
        for entry in fixture.request.failure_reason_catalog
    )

    assert len(admitted_rows) == 13
    assert expected_rows == admitted_rows


@pytest.mark.parametrize(
    (
        "case_id",
        "fault",
        "expected_outcome",
        "expected_stage",
        "expected_reason_id",
        "expected_materialization_state",
    ),
    _FAILURE_STAGE_MATRIX,
    ids=tuple(row[0] for row in _FAILURE_STAGE_MATRIX),
)
def test_every_failure_stage_selects_its_exact_reason_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    fault: str,
    expected_outcome: GeneratorOutcomeKind,
    expected_stage: GeneratorTerminalStage,
    expected_reason_id: str,
    expected_materialization_state: SourceMaterializationState,
) -> None:
    del case_id
    fixture = _failure_fixture(fault)
    _install_failure_fault(monkeypatch, fault)
    expected_entry = next(
        entry
        for entry in fixture.request.failure_reason_catalog
        if entry.reason.outcome_kind is expected_outcome
        and entry.reason.terminal_stage is expected_stage
    )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    assert output.kind is GeneratorInvocationOutputKind.FINAL
    record = output.payload.record
    terminal = record.terminal_reason_binding
    assert record.outcome_kind is expected_outcome
    assert record.terminal_stage is expected_stage
    assert record.source_event.materialization_state is expected_materialization_state
    assert type(terminal) is TerminalReasonFailure
    assert terminal.reason == expected_entry.reason
    assert terminal.reason_ref == expected_entry.reason_ref
    assert terminal.reason.reason_id == expected_reason_id
    assert terminal.occurrence.reason_ref == expected_entry.reason_ref
    assert terminal.occurrence.occurrence_evidence_binding.is_bound
    assert (
        terminal.occurrence.occurrence_evidence_binding.value
        == expected_entry.occurrence_evidence_fallback
    )
    assert record.attempt_record.outcome_kind is expected_outcome
    assert record.attempt_record.terminal_stage is expected_stage
    assert (
        record.attempt_record.failure_reason_binding.pair.record
        == expected_entry.reason
    )
    assert fixture.accounting_authority.calls == 1
    if fault.endswith("semantic"):
        assert expected_outcome is not GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    if fault.endswith("infrastructure"):
        assert expected_outcome is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE


def test_generation_failure_disposition_accounts_to_final_attempt_record() -> None:
    fixture = make_b03_fixture(support_mode="outside")

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    disposition = record.disposition_binding.pair.record
    state_payload = disposition.state_payload
    assert disposition.case_state is CaseState.GENERATION_FAILURE
    assert state_payload.state is CaseState.GENERATION_FAILURE
    assert type(state_payload.payload) is GenerationFailurePayload
    assert (
        state_payload.payload.accounting_ref.content_digest
        == record.attempt_record_ref.content_digest
    )
    assert (
        state_payload.payload.accounting_ref.content_digest
        != record.attempt_accounting_decision_ref.content_digest
    )


def test_accounting_owner_failure_is_a_distinct_final_infrastructure_outcome() -> None:
    fixture = make_b03_fixture(accounting_unavailable=True)

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    directive = record.attempt_accounting_decision.accounting_directive_pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY
    assert directive.directive_kind is AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE
    assert not record.case_binding.is_bound
    assert record.constructed_case_binding.is_bound
    assert not record.disposition_binding.is_bound
    assert output.payload.artifact is not None
    assert record.constructed_case_binding.pair.ref == output.payload.artifact.case_ref
    assert fixture.accounting_authority.calls == 1


def test_hostile_support_exception_is_sanitized_and_fails_closed() -> None:
    secret = "provider-secret-participant-workstation-token"

    class HostileSupportError(Exception):
        pass

    class HostileSupportAuthority:
        def __init__(self) -> None:
            self.calls = 0

        def assess_support_exclusion(self, request: object) -> object:
            del request
            self.calls += 1
            raise HostileSupportError(secret)

    fixture = make_b03_fixture()
    hostile = HostileSupportAuthority()

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=hostile,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    assert (
        output.payload.record.outcome_kind
        is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    )
    assert (
        output.payload.record.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    )
    assert hostile.calls == 1
    rendered = repr(output) + str(output)
    canonical = output.payload.record.canonical_bytes()
    assert secret not in rendered
    assert secret.encode() not in canonical


def _support_fallback(fixture: B03Fixture) -> object:
    return next(
        entry.occurrence_evidence_fallback
        for entry in fixture.request.failure_reason_catalog
        if entry.reason.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        and entry.reason.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    )


def _censor_fallback(fixture: B03Fixture) -> object:
    return next(
        entry.occurrence_evidence_fallback
        for entry in fixture.request.failure_reason_catalog
        if entry.reason.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        and entry.reason.terminal_stage is GeneratorTerminalStage.CENSORING_AUTHORITY
    )


def test_forged_support_contract_echo_is_rejected_to_admitted_fallback() -> None:
    fixture = make_b03_fixture()

    class ForgedSupportContractAuthority:
        def __init__(self) -> None:
            self.calls = 0

        def assess_support_exclusion(self, request: object) -> object:
            self.calls += 1
            decision = fixture.support_authority.assess_support_exclusion(request)
            forged = replace(
                decision.assessments[0],
                support_contract=fixture.bundle.primary_population.support_contract,
            )
            return replace(decision, assessments=(forged, decision.assessments[1]))

    authority = ForgedSupportContractAuthority()
    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    support = record.support_decision_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    assert support.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE
    assert support.infrastructure_failure_ref == _support_fallback(fixture)
    assert authority.calls == 1


def test_forged_assessment_unavailable_ref_is_rejected_to_admitted_fallback() -> None:
    fixture = make_b03_fixture()
    forged_failure = challenge_owner(
        "infrastructure_failure", "forged_assessment_failure"
    )

    class ForgedAssessmentFallbackAuthority:
        def assess_support_exclusion(self, request: object) -> object:
            decision = fixture.support_authority.assess_support_exclusion(request)
            primary = decision.assessments[1]
            reason = challenge_owner(
                "applicability_reason", "forged_assessment_not_applicable"
            )
            forged = replace(
                primary,
                decision_kind=PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE,
                applicability_evidence_binding=(
                    ApplicabilityBinding.not_applicable(reason)
                ),
                membership_evidence_binding=ApplicabilityBinding.not_applicable(reason),
                infrastructure_failure_binding=ApplicabilityBinding.bound(
                    forged_failure
                ),
            )
            return replace(
                decision,
                assessments=(decision.assessments[0], forged),
                terminal_resolution=(
                    PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE
                ),
                effective_assessment_role=PopulationAssessmentRole.PRIMARY_CASE,
                resolution_policy_ref=challenge_owner(
                    "policy_authority", "forged_support_resolution"
                ),
                resolution_evidence_ref=challenge_owner(
                    "membership_decision", "forged_support_resolution"
                ),
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=ForgedAssessmentFallbackAuthority(),
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    support = output.payload.record.support_decision_binding.pair.record
    assert support.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE
    assert support.infrastructure_failure_ref == _support_fallback(fixture)
    assert support.infrastructure_failure_ref != forged_failure


def test_forged_censor_failure_ref_is_rejected_to_admitted_fallback() -> None:
    fixture = make_b03_fixture()
    forged_failure = challenge_owner("infrastructure_failure", "forged_censor_failure")

    class ForgedCensorFallbackAuthority:
        def decide_censoring(self, request: object) -> CensoringVerdict:
            return CensoringVerdict(
                challenge_key=fixture.request.challenge_key,
                request=request,
                verdict_kind=CensoringVerdictKind.AUTHORITY_UNAVAILABLE,
                basis=None,
                infrastructure_failure_ref=forged_failure,
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=ForgedCensorFallbackAuthority(),
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    verdict = record.censoring_verdict_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.CENSORING_AUTHORITY
    assert verdict.verdict_kind is CensoringVerdictKind.AUTHORITY_UNAVAILABLE
    assert verdict.infrastructure_failure_ref == _censor_fallback(fixture)
    assert verdict.infrastructure_failure_ref != forged_failure


def test_support_interface_that_vanishes_after_admission_fails_closed() -> None:
    fixture = make_b03_fixture()

    class VanishingSupportAuthority:
        def __init__(self) -> None:
            self.lookups = 0

        def __getattribute__(self, name: str) -> object:
            if name == "assess_support_exclusion":
                lookups = object.__getattribute__(self, "lookups") + 1
                object.__setattr__(self, "lookups", lookups)
                if lookups == 1:
                    return lambda request: request
                raise AttributeError("vanished support interface")
            return object.__getattribute__(self, name)

    authority = VanishingSupportAuthority()
    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    support = record.support_decision_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    assert support.infrastructure_failure_ref == _support_fallback(fixture)
    assert authority.lookups == 2


def test_constructor_bypassed_support_decision_fails_closed() -> None:
    fixture = make_b03_fixture()

    class ForgedSupportAuthority:
        def assess_support_exclusion(self, request: object) -> object:
            decision = fixture.support_authority.assess_support_exclusion(request)
            return _constructor_bypass(
                decision,
                assessments=tuple(reversed(decision.assessments)),
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=ForgedSupportAuthority(),
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    support = record.support_decision_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    assert support.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE
    assert support.infrastructure_failure_ref == _support_fallback(fixture)


def test_constructor_bypassed_cross_challenge_support_evidence_fails_closed() -> None:
    fixture = make_b03_fixture()
    other_key = ChallengeKey("b03_other_challenge", "1.0")
    secret_id = "cross_challenge_secret_evidence"

    class CrossChallengeSupportAuthority:
        def assess_support_exclusion(self, request: object) -> object:
            decision = fixture.support_authority.assess_support_exclusion(request)
            primary = decision.assessments[1]
            forged_primary = _constructor_bypass(
                primary,
                applicability_evidence_binding=ApplicabilityBinding.bound(
                    challenge_owner(
                        "applicability_evidence",
                        secret_id,
                        challenge_key=other_key,
                    )
                ),
                membership_evidence_binding=ApplicabilityBinding.bound(
                    challenge_owner(
                        "membership_evidence",
                        secret_id,
                        challenge_key=other_key,
                    )
                ),
            )
            return _constructor_bypass(
                decision,
                assessments=(decision.assessments[0], forged_primary),
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=CrossChallengeSupportAuthority(),
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    support = record.support_decision_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    assert support.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE
    assert support.infrastructure_failure_ref == _support_fallback(fixture)
    rendered = repr(output) + str(output)
    canonical = record.canonical_bytes()
    assert secret_id not in rendered
    assert secret_id.encode() not in canonical


def test_constructor_bypassed_censoring_verdict_fails_closed() -> None:
    fixture = make_b03_fixture()

    class ForgedCensoringAuthority:
        def decide_censoring(self, request: object) -> object:
            verdict = fixture.censoring_authority.decide_censoring(request)
            return _constructor_bypass(
                verdict,
                verdict_kind=CensoringVerdictKind.CENSORED,
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=ForgedCensoringAuthority(),
        accounting_authority=fixture.accounting_authority,
    )

    record = output.payload.record
    verdict = record.censoring_verdict_binding.pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.CENSORING_AUTHORITY
    assert verdict.verdict_kind is CensoringVerdictKind.AUTHORITY_UNAVAILABLE
    assert verdict.infrastructure_failure_ref == _censor_fallback(fixture)


def test_constructor_bypassed_accounting_directive_fails_closed() -> None:
    fixture = make_b03_fixture()

    class ForgedAccountingAuthority:
        def decide_attempt_accounting(self, request: object) -> object:
            directive = fixture.accounting_authority.decide_attempt_accounting(request)
            return _constructor_bypass(
                directive,
                final_outcome=GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                final_stage=GeneratorTerminalStage.SUPPORT_AUTHORITY,
            )

    output = service.generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=ForgedAccountingAuthority(),
    )

    record = output.payload.record
    directive = record.attempt_accounting_decision.accounting_directive_pair.record
    assert record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert record.terminal_stage is GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY
    assert directive.directive_kind is AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE


def test_hostile_initial_authority_lookup_is_sanitized() -> None:
    fixture = make_b03_fixture()
    secret = "lookup-secret-participant-workstation-token"

    class HostileLookupAuthority:
        def __getattribute__(self, name: str) -> object:
            if name == "assess_support_exclusion":
                raise RuntimeError(secret)
            return object.__getattribute__(self, name)

    with pytest.raises(GeneratorValidationError) as caught:
        service.generate_fixture_case(
            fixture.request,
            fixture_authority=fixture.fixture_authority,
            support_authority=HostileLookupAuthority(),
            censoring_authority=fixture.censoring_authority,
            accounting_authority=fixture.accounting_authority,
        )

    error = caught.value
    assert error.code == GeneratorInputCode.AUTHORITY_INTERFACE_INVALID.value
    assert error.path == "/support_authority"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert secret not in str(error)
    assert secret not in repr(error)
