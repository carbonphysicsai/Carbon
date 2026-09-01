"""End-to-end deterministic B-03 fixture service tests."""

from __future__ import annotations

import threading
from dataclasses import replace

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.authoring.loading import load_authoring_bytes
from carbon.authoring.model import ApplicabilityTag
from carbon.authoring.physical import TimeMode
from carbon.generators import authorities as generator_authorities
from carbon.generators import service as generator_service
from carbon.generators.accounting import AttemptAccountingDirectiveKind
from carbon.generators.authorities import FixtureGenerationGrant
from carbon.generators.errors import (
    GeneratorInputCode,
    GeneratorServiceCode,
    GeneratorServiceError,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GeneratorInvocationOutputKind,
    GeneratorOutcomeKind,
    GeneratorTerminalStage,
)
from carbon.generators.service import generate_fixture_case
from carbon.registry.model import ChallengeKey


def _generate(fixture, *, request=None):
    return generate_fixture_case(
        fixture.request if request is None else request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )


def _forged_grant(grant: FixtureGenerationGrant, **updates: object) -> object:
    forged = object.__new__(FixtureGenerationGrant)
    for name in (
        "request",
        "replay_ref",
        "authoring_capability",
        "origin",
        "context",
        "draw_index",
        "projection",
    ):
        object.__setattr__(forged, name, updates.get(name, getattr(grant, name)))
    object.__setattr__(forged, "_FixtureGenerationGrant__lock", threading.Lock())
    object.__setattr__(forged, "_FixtureGenerationGrant__used", False)
    return forged


def _constructor_bypass(value: object, **updates: object) -> object:
    forged = object.__new__(type(value))
    for name in value.__dataclass_fields__:
        object.__setattr__(forged, name, updates.get(name, getattr(value, name)))
    return forged


def _assert_rejected_before_fixture_consumption(
    fixture,
    request,
    expected_code: GeneratorInputCode,
) -> None:
    with pytest.raises(GeneratorValidationError) as caught:
        _generate(fixture, request=request)

    assert caught.value.code == expected_code.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == (0, 0, 0)
    # A fixture grant consumes the reservation before acquiring provider entropy.
    # Its continued availability therefore proves neither boundary was crossed.
    fixture.fixture_authority.require_available(fixture.request.replay_ref)


def _dependency_ref_key(ref: object) -> tuple[object, ...]:
    return (
        ref.object_kind,
        ref.challenge_key.challenge_id,
        ref.challenge_key.version,
        ref.object_id,
        ref.object_version,
        ref.schema_version,
        ref.canonicalization_profile,
        ref.content_digest,
        getattr(ref, "expected_population_role", ""),
    )


def test_full_transient_eight_point_graph_generates_one_exact_valid_case() -> None:
    fixture = make_b03_fixture()
    physical = fixture.bundle.physical_system
    candidate = fixture.bundle.candidate_output

    assert physical.time_contract.mode is TimeMode.TRANSIENT
    assert physical.time_contract.time_coordinate_binding.is_bound
    assert candidate.time_horizon_binding.candidate_field_ids == ("candidate_time",)
    assert physical.causal_inputs[0].shape_contract[0].extent.fixed_extent == 8
    assert (
        physical.required_physical_quantities[0].shape_contract[0].extent.fixed_extent
        == 8
    )
    assert fixture.request.case_construction.applicability_bindings

    output = _generate(fixture)

    assert output.kind is GeneratorInvocationOutputKind.FINAL
    result = output.payload
    assert result.record.outcome_kind is GeneratorOutcomeKind.VALID_GENERATED
    assert result.record.terminal_stage is GeneratorTerminalStage.CENSORING_COMPLETION
    assert result.artifact is not None
    assert result.record.case_binding.is_bound
    assert result.record.constructed_case_binding.is_bound
    assert result.record.case_binding.pair.ref == result.artifact.case_ref
    assert result.record.constructed_case_binding.pair.ref == result.artifact.case_ref
    assert result.artifact.case.applicability_bindings == (
        fixture.request.case_construction.applicability_bindings
    )
    assert result.ref == result.record.to_ref()


@pytest.mark.parametrize(
    "forgery",
    ("exact_clone", "draw", "projection", "replay", "subclass", "partial"),
)
def test_forged_exact_grant_echoes_fail_at_context_acquisition(
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
) -> None:
    fixture = make_b03_fixture()
    original = generator_authorities.FixtureGenerationAuthority.issue_grant

    def issue_forged(self: object, request: object) -> object:
        grant = original(self, request)
        if forgery == "exact_clone":
            return _forged_grant(grant)
        if forgery == "draw":
            return _forged_grant(grant, draw_index=grant.draw_index + 1)
        if forgery == "projection":
            projection = grant.projection
            forged_projection = type(projection)._from_fixture_values(
                projection.exam_commitment,
                projection.challenge_id,
                projection.challenge_version,
                "2.0",
                projection.generator_digest,
                projection.scoring_version,
                projection.scoring_digest,
            )
            return _forged_grant(grant, projection=forged_projection)
        if forgery == "replay":
            return _forged_grant(
                grant,
                replay_ref=replace(
                    grant.replay_ref,
                    commitment_digest=("sha256:" + "a" * 64),
                ),
            )
        if forgery == "partial":
            partial = object.__new__(FixtureGenerationGrant)
            object.__setattr__(partial, "request", request)
            return partial

        class GrantSubclass(FixtureGenerationGrant):
            __slots__ = ()

        subclass = object.__new__(GrantSubclass)
        for name in (
            "request",
            "replay_ref",
            "authoring_capability",
            "origin",
            "context",
            "draw_index",
            "projection",
        ):
            object.__setattr__(subclass, name, getattr(grant, name))
        object.__setattr__(subclass, "_FixtureGenerationGrant__used", False)
        return subclass

    monkeypatch.setattr(
        generator_authorities.FixtureGenerationAuthority,
        "issue_grant",
        issue_forged,
    )
    output = _generate(fixture)
    result = output.payload

    assert result.record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert result.record.terminal_stage is GeneratorTerminalStage.CONTEXT_ACQUISITION
    assert fixture.support_authority.calls == 0
    assert fixture.censoring_authority.calls == 0
    assert fixture.accounting_authority.calls == 1


def test_generation_grant_is_token_gated_and_store_bound_to_exact_object() -> None:
    fixture = make_b03_fixture()
    authority = fixture.fixture_authority
    authority.claim_attempt(fixture.request)
    grant = authority.issue_grant(fixture.request)

    with pytest.raises(TypeError) as construction_rejected:
        FixtureGenerationGrant(
            request=grant.request,
            replay_ref=grant.replay_ref,
            authoring_capability=grant.authoring_capability,
            origin=grant.origin,
            context=grant.context,
            draw_index=grant.draw_index,
            projection=grant.projection,
        )
    assert construction_rejected.value.__cause__ is None
    assert construction_rejected.value.__context__ is None

    clone = _forged_grant(grant)
    with pytest.raises(GeneratorServiceError) as clone_rejected:
        authority.validate_grant(fixture.request, clone)
    assert clone_rejected.value.code == GeneratorServiceCode.AUTHORITY_UNAVAILABLE.value
    assert clone_rejected.value.__cause__ is None
    assert clone_rejected.value.__context__ is None
    state = authority._FixtureGenerationAuthority__reservations[
        fixture.request.replay_ref
    ]
    assert state.issued_grant is None
    assert state.grant_validated is False


def test_generation_grant_validation_is_one_shot_and_returns_issued_object() -> None:
    fixture = make_b03_fixture()
    authority = fixture.fixture_authority
    authority.claim_attempt(fixture.request)
    grant = authority.issue_grant(fixture.request)

    validated = authority.validate_grant(fixture.request, grant)
    assert validated is grant
    state = authority._FixtureGenerationAuthority__reservations[
        fixture.request.replay_ref
    ]
    assert state.issued_grant is None
    assert state.grant_validated is True

    with pytest.raises(GeneratorServiceError) as repeated:
        authority.validate_grant(fixture.request, grant)
    assert repeated.value.code == GeneratorServiceCode.AUTHORITY_UNAVAILABLE.value
    assert repeated.value.__cause__ is None
    assert repeated.value.__context__ is None


def test_concurrent_generation_grant_validation_accepts_exactly_once() -> None:
    fixture = make_b03_fixture()
    authority = fixture.fixture_authority
    authority.claim_attempt(fixture.request)
    grant = authority.issue_grant(fixture.request)
    start_barrier = threading.Barrier(2)
    validated: list[FixtureGenerationGrant] = []
    failures: list[Exception] = []

    def validate() -> None:
        start_barrier.wait(timeout=5)
        try:
            validated.append(authority.validate_grant(fixture.request, grant))
        except Exception as exc:  # noqa: BLE001 - collect the thread outcome.
            failures.append(exc)

    threads = (threading.Thread(target=validate), threading.Thread(target=validate))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert validated == [grant]
    assert len(failures) == 1
    assert type(failures[0]) is GeneratorServiceError
    assert failures[0].code == GeneratorServiceCode.AUTHORITY_UNAVAILABLE.value
    assert failures[0].__cause__ is None
    assert failures[0].__context__ is None
    state = authority._FixtureGenerationAuthority__reservations[
        fixture.request.replay_ref
    ]
    assert state.issued_grant is None
    assert state.grant_validated is True


def test_preconsumed_issued_grant_is_rejected_without_a_second_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_b03_fixture()
    original_issue = generator_authorities.FixtureGenerationAuthority.issue_grant
    original_derive = generator_authorities.derive_fixture_official_seed
    derive_calls = 0

    def count_derive(*args: object, **kwargs: object) -> object:
        nonlocal derive_calls
        derive_calls += 1
        return original_derive(*args, **kwargs)

    def issue_preconsumed(self: object, request: object) -> FixtureGenerationGrant:
        grant = original_issue(self, request)
        grant.derive_once(request.role_binding)
        return grant

    monkeypatch.setattr(
        generator_authorities,
        "derive_fixture_official_seed",
        count_derive,
    )
    monkeypatch.setattr(
        generator_authorities.FixtureGenerationAuthority,
        "issue_grant",
        issue_preconsumed,
    )

    result = _generate(fixture).payload

    assert result.record.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    assert result.record.terminal_stage is GeneratorTerminalStage.CONTEXT_ACQUISITION
    assert derive_calls == 1
    assert fixture.support_authority.calls == 0
    assert fixture.censoring_authority.calls == 0
    assert fixture.accounting_authority.calls == 1


def test_concurrent_generation_grant_derives_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_b03_fixture()
    fixture.fixture_authority.claim_attempt(fixture.request)
    grant = fixture.fixture_authority.issue_grant(fixture.request)
    grant = fixture.fixture_authority.validate_grant(fixture.request, grant)
    start_barrier = threading.Barrier(2)
    original_derive = generator_authorities.derive_fixture_official_seed
    derive_calls: list[object] = []

    def count_derive(*args: object, **kwargs: object) -> object:
        derive_calls.append(args)
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(
        generator_authorities,
        "derive_fixture_official_seed",
        count_derive,
    )
    derived: list[object] = []
    failures: list[Exception] = []

    def consume_grant() -> None:
        start_barrier.wait(timeout=5)
        try:
            derived.append(grant.derive_once(fixture.request.role_binding))
        except Exception as exc:  # noqa: BLE001 - collect the thread outcome.
            failures.append(exc)

    threads = (
        threading.Thread(target=consume_grant),
        threading.Thread(target=consume_grant),
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert len(derived) == 1
    assert len(derive_calls) == 1
    assert len(failures) == 1
    assert type(failures[0]) is GeneratorServiceError
    assert failures[0].code == GeneratorServiceCode.INTERNAL_FAILURE.value
    assert failures[0].__cause__ is None
    assert failures[0].__context__ is None


def test_partial_exact_grant_validation_has_no_exception_chain() -> None:
    fixture = make_b03_fixture()
    fixture.fixture_authority.claim_attempt(fixture.request)
    fixture.fixture_authority.issue_grant(fixture.request)
    partial = object.__new__(FixtureGenerationGrant)

    with pytest.raises(GeneratorServiceError) as rejected:
        fixture.fixture_authority.validate_grant(fixture.request, partial)

    assert rejected.value.code == GeneratorServiceCode.AUTHORITY_UNAVAILABLE.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None


def test_compatibility_terminal_claim_prevents_duplicate_attempt_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_b03_fixture()

    def incompatible(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ValueError("constructor compatibility rejected")

    monkeypatch.setattr(
        generator_service,
        "validate_candidate_against_physical",
        incompatible,
    )

    first = _generate(fixture).payload
    assert first.record.outcome_kind is GeneratorOutcomeKind.INVALID_CONSTRUCTION
    assert (
        first.record.terminal_stage is GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY
    )
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == (0, 0, 1)

    with pytest.raises(GeneratorValidationError) as rejected:
        _generate(fixture)
    assert rejected.value.code == GeneratorInputCode.REPLAY_RESERVATION_INVALID.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == (0, 0, 1)


def test_concurrent_post_admission_claim_allows_one_accounting_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_b03_fixture()
    admission_barrier = threading.Barrier(2)
    original_validate = generator_service.validate_generator_request

    def synchronized_validate(*args: object, **kwargs: object) -> object:
        admitted = original_validate(*args, **kwargs)
        admission_barrier.wait(timeout=5)
        return admitted

    monkeypatch.setattr(
        generator_service,
        "validate_generator_request",
        synchronized_validate,
    )
    outputs: list[object] = []
    failures: list[Exception] = []

    def run_generation() -> None:
        try:
            outputs.append(_generate(fixture))
        except Exception as exc:  # noqa: BLE001 - collect the thread outcome.
            failures.append(exc)

    threads = (
        threading.Thread(target=run_generation),
        threading.Thread(target=run_generation),
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads)
    assert len(outputs) == 1
    assert outputs[0].kind is GeneratorInvocationOutputKind.FINAL
    assert len(failures) == 1
    assert type(failures[0]) is GeneratorValidationError
    assert failures[0].code == GeneratorInputCode.REPLAY_RESERVATION_INVALID.value
    assert failures[0].__cause__ is None
    assert failures[0].__context__ is None
    assert (
        fixture.support_authority.calls,
        fixture.censoring_authority.calls,
        fixture.accounting_authority.calls,
    ) == (1, 1, 1)


def test_generator_id_and_recomputed_ref_alias_is_rejected_before_claim() -> None:
    fixture = make_b03_fixture()
    generator = replace(
        fixture.request.generator,
        generator_id="aliased_b03_fixture_generator",
    )
    request = replace(
        fixture.request,
        generator=generator,
        generator_ref=generator.to_ref(),
    )

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.STALE_BINDING,
    )


def test_generator_version_and_recomputed_ref_mismatch_remains_rejected() -> None:
    fixture = make_b03_fixture()
    generator = replace(
        fixture.request.generator,
        generator_version="2.0",
    )
    request = replace(
        fixture.request,
        generator=generator,
        generator_ref=generator.to_ref(),
    )

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.STALE_BINDING,
    )


def test_same_exact_authorized_fixture_request_is_byte_and_ref_deterministic() -> None:
    first_fixture = make_b03_fixture()
    second_fixture = make_b03_fixture()

    assert first_fixture.request.to_ref() == second_fixture.request.to_ref()
    first = _generate(first_fixture).payload
    second = _generate(second_fixture).payload

    assert (
        first.artifact.case.canonical_bytes() == second.artifact.case.canonical_bytes()
    )
    assert first.artifact.case_ref == second.artifact.case_ref
    assert first.record.canonical_bytes() == second.record.canonical_bytes()
    assert first.ref == second.ref


def test_equal_replay_values_are_bound_to_the_exact_issuing_store() -> None:
    first_fixture = make_b03_fixture()
    second_fixture = make_b03_fixture()

    assert first_fixture.request.replay_ref == second_fixture.request.replay_ref
    assert first_fixture.request.replay_ref is not second_fixture.request.replay_ref
    assert first_fixture.request.to_ref() == second_fixture.request.to_ref()

    with pytest.raises(GeneratorValidationError) as rejected:
        _generate(second_fixture, request=first_fixture.request)
    assert rejected.value.code == GeneratorInputCode.REPLAY_RESERVATION_INVALID.value
    assert rejected.value.path == "/replay_ref"
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert (
        second_fixture.support_authority.calls,
        second_fixture.censoring_authority.calls,
        second_fixture.accounting_authority.calls,
    ) == (0, 0, 0)

    second_fixture.fixture_authority.require_available(
        second_fixture.request.replay_ref
    )
    first = _generate(first_fixture).payload
    second = _generate(second_fixture).payload
    assert first.ref == second.ref


def test_one_request_executes_once_and_cannot_silently_retry() -> None:
    fixture = make_b03_fixture()
    output = _generate(fixture)
    record = output.payload.record
    directive = record.attempt_accounting_decision.accounting_directive_pair.record

    assert fixture.support_authority.calls == 1
    assert fixture.censoring_authority.calls == 1
    assert fixture.accounting_authority.calls == 1
    assert directive.directive_kind is AttemptAccountingDirectiveKind.FINAL
    assert (
        directive.successor_authorization_binding.tag is ApplicabilityTag.NOT_APPLICABLE
    )
    assert record.attempt_record.attempt_ordinal == 0
    assert record.attempt_record.attempt_ref == fixture.request.attempt_ref
    assert not record.attempt_record.pending_attempt_binding.is_bound

    with pytest.raises(GeneratorValidationError):
        _generate(fixture)

    assert fixture.support_authority.calls == 1
    assert fixture.censoring_authority.calls == 1
    assert fixture.accounting_authority.calls == 1


def test_cross_challenge_named_applicability_reason_is_rejected_at_admission() -> None:
    fixture = make_b03_fixture()
    other_key = ChallengeKey("b03_other_challenge", "1.0")
    first, *rest = fixture.request.attempt_accounting_applicability_reasons
    forged = replace(
        first,
        reason_ref=challenge_owner(
            "applicability_reason",
            "cross_challenge_runtime_reason",
            challenge_key=other_key,
        ),
    )
    request = replace(
        fixture.request,
        attempt_accounting_applicability_reasons=(forged, *rest),
    )

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.CROSS_CHALLENGE,
    )


def test_cross_challenge_failure_occurrence_fallback_is_rejected_at_admission() -> None:
    fixture = make_b03_fixture()
    other_key = ChallengeKey("b03_other_challenge", "1.0")
    first, *rest = fixture.request.failure_reason_catalog
    forged = _constructor_bypass(
        first,
        occurrence_evidence_fallback=challenge_owner(
            "audit_evidence",
            "cross_challenge_occurrence_fallback",
            challenge_key=other_key,
        ),
    )
    request = replace(
        fixture.request,
        failure_reason_catalog=(forged, *rest),
    )

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.CROSS_CHALLENGE,
    )


def test_forged_intended_unit_link_evidence_is_rejected_before_execution() -> None:
    fixture = make_b03_fixture()
    other_key = ChallengeKey("b03_other_challenge", "1.0")
    decision = fixture.request.intended_unit_link_decision
    forged = _constructor_bypass(
        decision,
        link_evidence_ref=challenge_owner(
            "authority_evidence",
            "cross_challenge_intended_link",
            challenge_key=other_key,
        ),
    )
    request = replace(
        fixture.request,
        intended_unit_link_decision=forged,
        intended_unit_link_decision_ref=forged.to_ref(),
    )

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.CROSS_CHALLENGE,
    )


def test_malformed_censoring_basis_maps_to_one_accounted_authority_failure() -> None:
    fixture = make_b03_fixture(censoring_mode="censored")
    nominal = fixture.censoring_authority
    other_key = ChallengeKey("b03_other_challenge", "1.0")

    class HostileCensoringAuthority:
        def __init__(self) -> None:
            self.calls = 0

        def decide_censoring(self, request: object) -> object:
            self.calls += 1
            verdict = nominal.decide_censoring(request)
            basis = _constructor_bypass(
                verdict.basis,
                audit_evidence_refs=(
                    challenge_owner(
                        "audit_evidence",
                        "cross_challenge_censor_audit",
                        challenge_key=other_key,
                    ),
                ),
            )
            return _constructor_bypass(verdict, basis=basis)

    hostile = HostileCensoringAuthority()
    fixture.censoring_authority = hostile  # type: ignore[assignment]

    output = _generate(fixture)

    assert output.kind is GeneratorInvocationOutputKind.FINAL
    assert (
        output.payload.record.outcome_kind
        is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
    )
    assert (
        output.payload.record.terminal_stage
        is GeneratorTerminalStage.CENSORING_AUTHORITY
    )
    assert hostile.calls == 1
    assert fixture.support_authority.calls == 1
    assert fixture.accounting_authority.calls == 1


def test_cross_challenge_case_representation_is_rejected_at_admission() -> None:
    fixture = make_b03_fixture()
    other_key = ChallengeKey("b03_other_challenge", "1.0")
    construction = replace(
        fixture.request.case_construction,
        case_representation_ref=challenge_owner(
            "representation",
            "cross_challenge_case_representation",
            challenge_key=other_key,
        ),
    )
    request = replace(fixture.request, case_construction=construction)

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.CROSS_CHALLENGE,
    )


def test_extra_unreachable_loaded_dependency_is_rejected_at_admission() -> None:
    fixture = make_b03_fixture()
    bundle = fixture.request.authoring_bundle
    extra_physical = replace(
        bundle.physical_system,
        object_id="unreachable_physical_system",
    )
    extra_ref = extra_physical.to_ref()
    physical_load = next(
        item
        for item in bundle.loaded_dependencies
        if item.expected_ref == bundle.physical_system_ref
    )
    extra_load = load_authoring_bytes(
        extra_ref,
        extra_physical.canonical_bytes(),
        origin=physical_load.origin,
        origin_evidence_ref=challenge_owner(
            "authoring_origin_evidence",
            "unreachable_physical_origin",
        ),
        source_provenance_refs=physical_load.source_provenance_refs,
        audit_evidence_refs=physical_load.audit_evidence_refs,
        qualification_evidence=physical_load.qualification_evidence,
    )
    resolved = tuple(
        sorted(
            (*bundle.resolved_dependencies, (extra_ref, extra_physical)),
            key=lambda pair: _dependency_ref_key(pair[0]),
        )
    )
    loaded_by_ref = {
        item.expected_ref: item for item in (*bundle.loaded_dependencies, extra_load)
    }
    loaded = tuple(loaded_by_ref[ref] for ref, _ in resolved)
    expanded_bundle = replace(
        bundle,
        resolved_dependencies=resolved,
        loaded_dependencies=loaded,
    )
    request = replace(fixture.request, authoring_bundle=expanded_bundle)

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.INVALID_VALUE,
    )


def test_reordered_resolved_and_loaded_dependencies_are_rejected_at_admission() -> None:
    fixture = make_b03_fixture()
    bundle = fixture.request.authoring_bundle
    reordered_bundle = replace(
        bundle,
        resolved_dependencies=tuple(reversed(bundle.resolved_dependencies)),
        loaded_dependencies=tuple(reversed(bundle.loaded_dependencies)),
    )
    request = replace(fixture.request, authoring_bundle=reordered_bundle)

    _assert_rejected_before_fixture_consumption(
        fixture,
        request,
        GeneratorInputCode.INVALID_VALUE,
    )
