"""Focused B-03 conformance, replay, duplicate, and external-fact proof."""

from __future__ import annotations

import hashlib
import pickle
import threading
from dataclasses import fields, replace
from inspect import signature

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.authoring.model import ApplicabilityBinding
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.generators import authorities as generator_authorities
from carbon.generators import canonical
from carbon.generators.accounting import (
    build_generation_attempt_record,
    build_intended_unit_accounting,
)
from carbon.generators.authorities import (
    FixtureGenerationAuthority,
    FixtureReplayDerivationCapability,
    FixtureReplayProbeAuthority,
)
from carbon.generators.conformance import (
    CONFORMANCE_FALLBACK_SCHEMA,
    ComparisonCorpusAvailability,
    ComparisonCorpusDecision,
    DeterministicReplayComparison,
    DuplicateComparisonRequest,
    DuplicateConformanceFacts,
    ExternalDistributionFactDecision,
    ExternalDistributionFactKind,
    ExternalDistributionFactRequest,
    ExternalDistributionFactSet,
    ExternalFactAvailability,
    ExternalFactAvailabilityKind,
    FixtureReplayProbe,
    FixtureReplayProbeRecord,
    GeneratorConformanceFacts,
    NearDuplicateDecision,
    NearDuplicateDecisionKind,
    NearDuplicateRequest,
    PostResultDuplicateRequest,
    ReplayIdentityFacts,
    build_duplicate_conformance_facts,
    build_external_distribution_fact_request,
    build_external_distribution_fact_set,
    build_fixture_replay_probe,
    build_generator_conformance_facts,
    compare_fixture_replay,
)
from carbon.generators.disclosure import create_public_generation_projection
from carbon.generators.errors import (
    GeneratorDisclosureError,
    GeneratorInputCode,
    GeneratorServiceCode,
    GeneratorServiceError,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GeneratorOutcomeKind,
    GeneratorResult,
    RecordRefBinding,
    RecordRefPair,
)
from carbon.generators.service import generate_fixture_case
from carbon.registry.model import ChallengeKey


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def _key() -> ChallengeKey:
    return ChallengeKey("b03_conformance_fixture", "1.0")


def _owner(kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(_key()),
        object_id=object_id,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{object_id}"),
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


def _generate_fixture_result(
    *,
    support_mode: str = "within",
    censoring_mode: str = "not_censored",
):
    fixture = make_b03_fixture(
        support_mode=support_mode,
        censoring_mode=censoring_mode,
    )
    output = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    return fixture, output.payload


def _replay_state(fixture: object) -> object:
    reservations = fixture.fixture_authority._FixtureGenerationAuthority__reservations
    return reservations[fixture.request.replay_ref]


def test_conformance_fallback_schema_is_exact_closed_and_ordered() -> None:
    assert CONFORMANCE_FALLBACK_SCHEMA == (
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
    assert len(set(CONFORMANCE_FALLBACK_SCHEMA)) == 16


def test_conformance_rejects_arbitrary_same_challenge_applicability_reason() -> None:
    _, result = _generate_fixture_result()
    facts = result.record.conformance_facts
    forged_binding = ApplicabilityBinding.not_applicable(
        challenge_owner(
            "applicability_reason",
            "arbitrary_same_challenge_conformance_reason",
        )
    )
    forged_replay = replace(
        facts.replay_identity_facts,
        constructed_case_facts_binding=forged_binding,
    )

    with pytest.raises(GeneratorValidationError):
        replace(
            facts,
            validated_case_facts_binding=forged_binding,
            replay_identity_facts=forged_replay,
        )

    forged = _constructor_bypass(
        facts,
        validated_case_facts_binding=forged_binding,
        replay_identity_facts=forged_replay,
    )
    encoded = canonical.canonical_bytes(forged)
    with pytest.raises(GeneratorValidationError):
        canonical.decode_canonical_bytes(encoded, GeneratorConformanceFacts)


def test_conformance_rejects_validated_case_without_support_binding() -> None:
    fixture, result = _generate_fixture_result()
    facts = result.record.conformance_facts
    support_inapplicable = RecordRefBinding.not_applicable(
        fixture.request.conformance_fallbacks[7].fallback_ref
    )

    with pytest.raises(GeneratorValidationError):
        replace(facts, support_decision_binding=support_inapplicable)

    forged = _constructor_bypass(
        facts,
        support_decision_binding=support_inapplicable,
    )
    encoded = canonical.canonical_bytes(forged)
    with pytest.raises(GeneratorValidationError):
        canonical.decode_canonical_bytes(encoded, GeneratorConformanceFacts)


def test_support_owner_unavailable_must_use_identity_fallback() -> None:
    _, result = _generate_fixture_result(support_mode="unavailable")
    facts = result.record.conformance_facts
    decision = facts.support_decision_binding.pair.record
    forged_decision = replace(
        decision,
        infrastructure_failure_ref=challenge_owner(
            "infrastructure_failure",
            "arbitrary_support_owner_failure",
        ),
    )
    forged_binding = RecordRefBinding.bound(
        forged_decision,
        forged_decision.to_ref(),
    )

    with pytest.raises(GeneratorValidationError):
        replace(facts, support_decision_binding=forged_binding)


def test_nominal_replay_probe_proves_all_exact_equalities_and_is_one_use() -> None:
    fixture, result = _generate_fixture_result()
    replay_authority = fixture.fixture_authority.replay_probe_authority()
    assert replay_authority is fixture.fixture_authority.replay_probe_authority()

    probe = build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=replay_authority,
    )
    comparison, comparison_ref = compare_fixture_replay(
        baseline_result=result,
        baseline_result_ref=result.ref,
        probe=probe,
        probe_ref=probe.ref,
    )

    payload_facts = result.record.conformance_facts.payload_facts_binding.value
    baseline_fingerprint = payload_facts.physical_payload_fingerprint
    baseline_case = result.artifact.case
    assert comparison_ref == comparison.to_ref()
    assert comparison.physical_payload_fingerprint_equal is True
    assert comparison.source_event_bytes_and_ref_equal is True
    assert comparison.case_bytes_and_ref_equal is True
    assert (
        baseline_fingerprint.to_ref()
        == probe.record.observed_physical_payload_fingerprint_ref
    )
    assert (
        baseline_fingerprint.canonical_bytes()
        == probe.record.observed_physical_payload_fingerprint.canonical_bytes()
    )
    assert result.record.source_event_ref == probe.source_event.to_ref()
    assert (
        result.record.source_event.canonical_bytes()
        == probe.source_event.canonical_bytes()
    )
    assert baseline_case.to_ref() == probe.case.to_ref()
    assert baseline_case.canonical_bytes() == probe.case.canonical_bytes()

    with pytest.raises(GeneratorServiceError) as reused:
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=replay_authority,
        )
    assert reused.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value


def test_concurrent_replay_claim_allows_exactly_one_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, result = _generate_fixture_result()
    authority = fixture.fixture_authority.replay_probe_authority()
    projection_barrier = threading.Barrier(2)
    original_projection = generator_authorities.create_fixture_official_exam_projection

    def synchronized_projection(context: object) -> object:
        try:
            projection_barrier.wait(timeout=0.25)
        except threading.BrokenBarrierError:
            pass
        return original_projection(context)

    monkeypatch.setattr(
        generator_authorities,
        "create_fixture_official_exam_projection",
        synchronized_projection,
    )
    probes: list[object] = []
    failures: list[Exception] = []

    def run_probe() -> None:
        try:
            probes.append(
                build_fixture_replay_probe(
                    baseline_result=result,
                    baseline_result_ref=result.ref,
                    baseline_request=fixture.request,
                    replay_authority=authority,
                )
            )
        except Exception as exc:  # noqa: BLE001 - collect the thread outcome.
            failures.append(exc)

    threads = (threading.Thread(target=run_probe), threading.Thread(target=run_probe))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert len(probes) == 1
    assert len(failures) == 1
    assert type(failures[0]) is GeneratorServiceError
    assert failures[0].code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert failures[0].__cause__ is None
    assert failures[0].__context__ is None
    assert _replay_state(fixture).probe_available is False


def test_censored_case_bearing_result_supports_one_exact_replay() -> None:
    fixture, result = _generate_fixture_result(censoring_mode="censored")
    authority = fixture.fixture_authority.replay_probe_authority()

    assert result.record.outcome_kind is GeneratorOutcomeKind.CENSORED_CASE
    assert result.artifact is not None
    probe = build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=authority,
    )
    comparison, _ = compare_fixture_replay(
        baseline_result=result,
        baseline_result_ref=result.ref,
        probe=probe,
        probe_ref=probe.ref,
    )
    assert comparison.physical_payload_fingerprint_equal is True
    assert comparison.source_event_bytes_and_ref_equal is True
    assert comparison.case_bytes_and_ref_equal is True

    with pytest.raises(GeneratorServiceError) as reused:
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=authority,
        )
    assert reused.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value


def test_replay_authority_and_private_state_are_redacted_nonserializable() -> None:
    fixture, result = _generate_fixture_result()
    authority = fixture.fixture_authority.replay_probe_authority()
    state = _replay_state(fixture)
    capability = state.replay_capability

    assert repr(authority) == "FixtureReplayProbeAuthority(<protected>)"
    assert str(authority) == repr(authority)
    assert repr(state) == "_ReplayReservation(<protected>)"
    assert str(state) == repr(state)
    assert type(capability) is FixtureReplayDerivationCapability
    assert repr(capability) == "FixtureReplayDerivationCapability(<protected>)"
    assert str(capability) == repr(capability)
    assert not hasattr(state, "context")
    assert not hasattr(state, "draw_index")
    assert not hasattr(fixture.fixture_authority, "take_replay_capability")
    for name in (
        "context",
        "draw_index",
        "derive_once",
        "replay_capability",
        "reservations",
    ):
        assert not hasattr(authority, name)
    with pytest.raises(TypeError):
        FixtureReplayProbeAuthority()
    with pytest.raises(TypeError):
        FixtureReplayDerivationCapability()
    for value in (authority, state, capability):
        with pytest.raises(TypeError):
            pickle.dumps(value)
        with pytest.raises(TypeError):
            value.__reduce__()
        with pytest.raises(TypeError):
            value.__reduce_ex__(4)

    build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=authority,
    )
    with pytest.raises(GeneratorServiceError) as consumed:
        capability._derive_once(fixture.request.role_binding)
    assert consumed.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert consumed.value.__cause__ is None
    assert consumed.value.__context__ is None


def test_concurrent_reservations_receive_distinct_store_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_b03_fixture()
    authority = fixture.fixture_authority
    encoding_barrier = threading.Barrier(2)
    original_encode = generator_authorities.encode_value

    def synchronized_encode(value: object) -> bytes:
        try:
            encoding_barrier.wait(timeout=0.25)
        except threading.BrokenBarrierError:
            pass
        return original_encode(value)

    monkeypatch.setattr(generator_authorities, "encode_value", synchronized_encode)
    replay_refs: list[object] = []
    failures: list[Exception] = []

    def reserve() -> None:
        try:
            replay_refs.append(authority.reserve_replay())
        except Exception as exc:  # noqa: BLE001 - collect the thread outcome.
            failures.append(exc)

    threads = (threading.Thread(target=reserve), threading.Thread(target=reserve))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert failures == []
    assert len(replay_refs) == 2
    assert replay_refs[0] != replay_refs[1]
    reservations = authority._FixtureGenerationAuthority__reservations
    assert all(replay_ref in reservations for replay_ref in replay_refs)


def test_wrong_replay_authority_store_rejects_same_challenge_baseline() -> None:
    fixture, result = _generate_fixture_result()
    wrong_authority = FixtureGenerationAuthority(
        provider=fixture.fixture_authority._FixtureGenerationAuthority__provider,
        pin=fixture.fixture_authority._FixtureGenerationAuthority__pin,
        generator=fixture.request.generator,
        generator_ref=fixture.request.generator_ref,
        reservation_issuer_ref=challenge_owner(
            "authority_evidence",
            "different_replay_store",
        ),
        fixture_registration_ref=fixture.request.generator.fixture_registration_ref,
        source_provenance_refs=fixture.request.generator.source_provenance_refs,
    )
    wrong_authority.reserve_replay()

    with pytest.raises(GeneratorServiceError) as rejected:
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=wrong_authority.replay_probe_authority(),
        )
    assert rejected.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert _replay_state(fixture).probe_available is True


def test_same_issuer_replay_stores_require_the_exact_issued_baseline() -> None:
    first_fixture, first_result = _generate_fixture_result()
    second_fixture, second_result = _generate_fixture_result()

    # Canonical commitments remain deterministic.  Store authority instead
    # comes from the exact noncanonical request/result wrappers retained when
    # each service invocation was issued.
    assert first_fixture.request.replay_ref == second_fixture.request.replay_ref
    assert first_result.ref == second_result.ref

    with pytest.raises(GeneratorServiceError) as rejected:
        build_fixture_replay_probe(
            baseline_result=first_result,
            baseline_result_ref=first_result.ref,
            baseline_request=first_fixture.request,
            replay_authority=(
                second_fixture.fixture_authority.replay_probe_authority()
            ),
        )
    assert rejected.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert _replay_state(first_fixture).probe_available is True
    assert _replay_state(second_fixture).probe_available is True

    assert (
        build_fixture_replay_probe(
            baseline_result=second_result,
            baseline_result_ref=second_result.ref,
            baseline_request=second_fixture.request,
            replay_authority=(
                second_fixture.fixture_authority.replay_probe_authority()
            ),
        ).record.baseline_result_ref
        == second_result.ref
    )
    assert _replay_state(first_fixture).probe_available is True


def test_noncase_and_forged_artifact_rejections_do_not_consume_probe() -> None:
    excluded_fixture, excluded = _generate_fixture_result(support_mode="excluded")
    with pytest.raises(GeneratorValidationError):
        build_fixture_replay_probe(
            baseline_result=excluded,
            baseline_result_ref=excluded.ref,
            baseline_request=excluded_fixture.request,
            replay_authority=(
                excluded_fixture.fixture_authority.replay_probe_authority()
            ),
        )
    assert _replay_state(excluded_fixture).probe_available is True
    assert _replay_state(excluded_fixture).baseline_result is None

    fixture, result = _generate_fixture_result()
    forged_artifact = _constructor_bypass(
        result.artifact,
        case_ref=replace(
            result.artifact.case_ref,
            content_digest=_digest("forged-replay-artifact"),
        ),
    )
    forged_result = _constructor_bypass(result, artifact=forged_artifact)
    replay_authority = fixture.fixture_authority.replay_probe_authority()
    with pytest.raises(GeneratorValidationError):
        build_fixture_replay_probe(
            baseline_result=forged_result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=replay_authority,
        )
    assert _replay_state(fixture).probe_available is True
    assert (
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=replay_authority,
        ).record.baseline_result_ref
        == result.ref
    )

    event_fixture, event_result = _generate_fixture_result()
    forged_event = _constructor_bypass(
        event_result.record.source_event,
        replay_ref=replace(
            event_result.record.source_event.replay_ref,
            commitment_digest=_digest("forged-nested-replay-event"),
        ),
    )
    forged_record = _constructor_bypass(
        event_result.record,
        source_event=forged_event,
    )
    forged_nested_result = _constructor_bypass(
        event_result,
        record=forged_record,
    )
    event_authority = event_fixture.fixture_authority.replay_probe_authority()
    with pytest.raises(GeneratorValidationError):
        build_fixture_replay_probe(
            baseline_result=forged_nested_result,
            baseline_result_ref=event_result.ref,
            baseline_request=event_fixture.request,
            replay_authority=event_authority,
        )
    assert _replay_state(event_fixture).probe_available is True
    assert (
        build_fixture_replay_probe(
            baseline_result=event_result,
            baseline_result_ref=event_result.ref,
            baseline_request=event_fixture.request,
            replay_authority=event_authority,
        ).record.baseline_result_ref
        == event_result.ref
    )


@pytest.mark.parametrize(
    "field_name",
    ("request_identity", "request_ref", "projection", "replay_capability"),
)
def test_private_replay_state_mismatch_rejects_before_consumption(
    field_name: str,
) -> None:
    fixture, result = _generate_fixture_result()
    state = _replay_state(fixture)
    original = getattr(state, field_name)
    setattr(state, field_name, None)

    with pytest.raises(GeneratorServiceError) as rejected:
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=fixture.fixture_authority.replay_probe_authority(),
        )
    assert rejected.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert state.probe_available is True
    setattr(state, field_name, original)
    assert (
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=fixture.fixture_authority.replay_probe_authority(),
        ).record.baseline_result_ref
        == result.ref
    )


@pytest.mark.parametrize("failure_site", ("derive", "materialize"))
def test_post_claim_replay_failure_is_sanitized_and_remains_consumed(
    monkeypatch: pytest.MonkeyPatch,
    failure_site: str,
) -> None:
    fixture, result = _generate_fixture_result()
    authority = fixture.fixture_authority.replay_probe_authority()

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("SECRET_REPLAY_FAILURE")

    target = (
        generator_authorities
        if failure_site == "derive"
        else __import__("carbon.generators.burgers", fromlist=["unused"])
    )
    attribute = (
        "derive_fixture_official_seed"
        if failure_site == "derive"
        else "_materialize_burgers_fixture_payload"
    )
    with monkeypatch.context() as patch:
        patch.setattr(target, attribute, fail)
        with pytest.raises(GeneratorServiceError) as rejected:
            build_fixture_replay_probe(
                baseline_result=result,
                baseline_result_ref=result.ref,
                baseline_request=fixture.request,
                replay_authority=authority,
            )
    assert rejected.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert "SECRET_REPLAY_FAILURE" not in repr(rejected.value)
    assert _replay_state(fixture).probe_available is False

    with pytest.raises(GeneratorServiceError) as reused:
        build_fixture_replay_probe(
            baseline_result=result,
            baseline_result_ref=result.ref,
            baseline_request=fixture.request,
            replay_authority=authority,
        )
    assert reused.value.code == GeneratorServiceCode.REPLAY_UNAVAILABLE.value
    assert reused.value.__cause__ is None
    assert reused.value.__context__ is None


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    (
        ("stale_baseline", GeneratorInputCode.STALE_BINDING),
        ("stale_request", GeneratorInputCode.STALE_BINDING),
        ("stale_ref", GeneratorInputCode.STALE_BINDING),
        ("cross_challenge", GeneratorInputCode.CROSS_CHALLENGE),
    ),
)
def test_replay_probe_rejects_stale_and_cross_challenge_inputs(
    mode: str,
    expected_code: GeneratorInputCode,
) -> None:
    fixture, result = _generate_fixture_result()
    replay_authority = fixture.fixture_authority.replay_probe_authority()
    baseline = result
    baseline_ref = result.ref
    request = fixture.request
    if mode == "stale_baseline":
        baseline = _constructor_bypass(
            result,
            ref=replace(result.ref, content_digest=_digest("stale-baseline")),
        )
    elif mode == "stale_request":
        request = replace(
            fixture.request,
            source_payload_inapplicable_reason_ref=challenge_owner(
                "applicability_reason",
                "stale_replay_request_payload_reason",
            ),
        )
    elif mode == "stale_ref":
        baseline_ref = replace(
            result.ref,
            content_digest=_digest("stale-result-ref"),
        )
    else:
        baseline_ref = replace(
            result.ref,
            challenge_key=ChallengeKey("b03_other_challenge", "1.0"),
        )

    with pytest.raises(GeneratorValidationError) as rejected:
        build_fixture_replay_probe(
            baseline_result=baseline,
            baseline_result_ref=baseline_ref,
            baseline_request=request,
            replay_authority=replay_authority,
        )
    assert rejected.value.code == expected_code.value
    probe = build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=replay_authority,
    )
    assert probe.record.baseline_result_ref == result.ref


def test_replay_probe_is_excluded_from_runtime_and_public_builders() -> None:
    fixture, result = _generate_fixture_result()
    probe = build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=fixture.fixture_authority.replay_probe_authority(),
    )
    probe_pair = RecordRefPair(probe.record, probe.ref)
    record = result.record
    attempt = record.attempt_record
    accounting = record.attempt_accounting_decision

    with pytest.raises(GeneratorValidationError):
        build_generation_attempt_record(
            request=fixture.request,
            source_event=record.source_event,
            accounting_decision=accounting,
            accounting_decision_ref=record.attempt_accounting_decision_ref,
            case_ref_binding=attempt.case_ref_binding,
            support_decision_binding=attempt.support_decision_binding,
            censoring_verdict_binding=attempt.censoring_verdict_binding,
            censoring_decision_binding=attempt.censoring_decision_binding,
            conformance_facts_pair=probe_pair,
            failure_reason_binding=attempt.failure_reason_binding,
            failure_occurrence_binding=attempt.failure_occurrence_binding,
            pending_attempt_binding=attempt.pending_attempt_binding,
        )
    with pytest.raises(GeneratorValidationError):
        GeneratorResult(record=probe.record, ref=probe.ref, artifact=None)
    with pytest.raises(GeneratorValidationError):
        build_intended_unit_accounting(
            link_decision_pairs=(
                RecordRefPair(
                    fixture.request.intended_unit_link_decision,
                    fixture.request.intended_unit_link_decision_ref,
                ),
            ),
            attempt_record_pairs=(probe_pair,),
            pending_attempt_pairs=(),
            accounting_directive_pairs=(accounting.accounting_directive_pair,),
            accounting_decision_pairs=(
                RecordRefPair(accounting, record.attempt_accounting_decision_ref),
            ),
        )
    with pytest.raises(GeneratorDisclosureError):
        create_public_generation_projection(probe)


def test_conformance_and_replay_field_inventories_are_literal() -> None:
    assert tuple(item.name for item in fields(ReplayIdentityFacts)) == (
        "request_identity",
        "request_ref",
        "source_event",
        "source_event_ref",
        "replay_ref",
        "generator_ref",
        "environment_ref",
        "fixture_configuration_ref",
        "role_binding",
        "materialization_state",
        "payload_facts_binding",
        "constructed_case_facts_binding",
    )
    assert tuple(item.name for item in fields(GeneratorConformanceFacts)) == (
        "challenge_key",
        "request_identity",
        "request_ref",
        "source_event",
        "source_event_ref",
        "generator_ref",
        "environment_ref",
        "fixture_configuration_ref",
        "primary_population_ref",
        "selection_population_ref",
        "sampling_plan_ref",
        "role_binding",
        "outcome_kind",
        "terminal_stage",
        "payload_facts_binding",
        "support_decision_binding",
        "validated_case_facts_binding",
        "replay_identity_facts",
    )
    assert tuple(item.name for item in fields(FixtureReplayProbeRecord)) == (
        "baseline_result",
        "baseline_result_ref",
        "baseline_request_identity",
        "baseline_request_ref",
        "replay_ref",
        "generator_ref",
        "environment_ref",
        "fixture_configuration_ref",
        "role_binding",
        "observed_physical_payload_fingerprint",
        "observed_physical_payload_fingerprint_ref",
        "reconstructed_protected_payload_ref",
        "reconstructed_source_event_ref",
        "reconstructed_case_ref",
    )
    assert tuple(item.name for item in fields(FixtureReplayProbe)) == (
        "record",
        "ref",
        "protected_payload",
        "source_event",
        "case",
    )
    assert tuple(item.name for item in fields(DeterministicReplayComparison)) == (
        "baseline_result_ref",
        "baseline_source_event_ref",
        "baseline_physical_payload_fingerprint_ref",
        "baseline_case_ref",
        "probe",
        "probe_ref",
        "observed_physical_payload_fingerprint_ref",
        "reconstructed_protected_payload_ref",
        "reconstructed_source_event_ref",
        "reconstructed_case_ref",
        "physical_payload_fingerprint_equal",
        "source_event_bytes_and_ref_equal",
        "case_bytes_and_ref_equal",
    )


def test_replay_comparison_owns_serialization_rejection_before_nested_values() -> None:
    sentinel = object.__new__(DeterministicReplayComparison)
    for item in fields(DeterministicReplayComparison):
        object.__setattr__(sentinel, item.name, "CALLER_VISIBLE_SENTINEL")

    expected = "DeterministicReplayComparison does not support generic serialization"
    for operation in (
        lambda: sentinel.__reduce__(),
        lambda: sentinel.__reduce_ex__(4),
        lambda: pickle.dumps(sentinel),
    ):
        with pytest.raises(TypeError) as rejected:
            operation()
        assert str(rejected.value) == expected


def test_duplicate_field_inventories_and_variants_are_closed() -> None:
    assert tuple(ComparisonCorpusAvailability) == (
        ComparisonCorpusAvailability.BOUND,
        ComparisonCorpusAvailability.OWNER_UNAVAILABLE,
    )
    assert tuple(NearDuplicateDecisionKind) == (
        NearDuplicateDecisionKind.DISTINCT,
        NearDuplicateDecisionKind.NEAR_DUPLICATE,
        NearDuplicateDecisionKind.POLICY_UNAVAILABLE,
    )
    assert tuple(item.name for item in fields(PostResultDuplicateRequest)) == (
        "challenge_key",
        "subject_result",
        "subject_result_ref",
        "case_representation_ref",
        "fixture_configuration_ref",
        "corpus_owner_unavailable_reason_ref",
        "near_duplicate_policy_unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(ComparisonCorpusDecision)) == (
        "request",
        "availability",
        "corpus_results",
        "corpus_issuance_ref",
        "unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(DuplicateComparisonRequest)) == (
        "subject_case_ref",
        "subject_physical_payload_fingerprint",
        "subject_physical_payload_fingerprint_ref",
        "corpus_decision",
        "corpus_decision_ref",
        "corpus_case_refs",
        "corpus_physical_payload_fingerprints",
        "corpus_physical_payload_fingerprint_refs",
    )
    assert tuple(item.name for item in fields(NearDuplicateRequest)) == (
        "post_result_request",
        "corpus_decision",
        "corpus_decision_ref",
        "duplicate_rule_ref",
        "semantic_equivalence_ref",
        "policy_unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(NearDuplicateDecision)) == (
        "request",
        "decision_kind",
        "semantic_equivalence_ref",
        "fact_ref",
        "audit_evidence_ref",
        "duplicate_rule_ref",
        "unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(DuplicateConformanceFacts)) == (
        "challenge_key",
        "post_result_request",
        "corpus_decision",
        "corpus_decision_ref",
        "duplicate_comparison_request_binding",
        "canonical_case_duplicate_binding",
        "physical_instance_collision_binding",
        "near_duplicate_decision_binding",
    )


def test_external_fact_inventories_and_variants_are_closed() -> None:
    assert tuple(ExternalDistributionFactKind) == (
        ExternalDistributionFactKind.REALIZED_STRATUM,
        ExternalDistributionFactKind.TAIL_ALLOCATION,
        ExternalDistributionFactKind.MARGINAL,
        ExternalDistributionFactKind.JOINT,
        ExternalDistributionFactKind.CONDITIONAL,
        ExternalDistributionFactKind.CENSORING_BY_CAUSE,
        ExternalDistributionFactKind.CENSORING_BY_STRATUM,
    )
    assert tuple(ExternalFactAvailabilityKind) == (
        ExternalFactAvailabilityKind.BOUND,
        ExternalFactAvailabilityKind.OWNER_UNAVAILABLE,
    )
    assert tuple(item.name for item in fields(ExternalDistributionFactRequest)) == (
        "challenge_key",
        "result_pairs",
        "intended_unit_pairs",
        "accounting_summary",
        "accounting_summary_ref",
        "sampling_plan_ref",
        "primary_population_ref",
        "selection_population_ref",
        "requested_fact_kind",
        "statistics_objective_ref",
        "owner_unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(ExternalFactAvailability)) == (
        "availability",
        "fact_kind",
        "statistics_objective_ref",
        "fact_ref",
        "audit_evidence_ref",
        "unavailable_reason_ref",
    )
    assert tuple(item.name for item in fields(ExternalDistributionFactDecision)) == (
        "request",
        "availability",
    )
    assert tuple(item.name for item in fields(ExternalDistributionFactSet)) == (
        "challenge_key",
        "result_pairs",
        "intended_unit_pairs",
        "accounting_summary",
        "accounting_summary_ref",
        "sampling_plan_ref",
        "primary_population_ref",
        "selection_population_ref",
        "decisions",
    )


def test_all_conformance_canonical_schemas_match_dataclass_fields() -> None:
    top_level = (
        GeneratorConformanceFacts,
        FixtureReplayProbeRecord,
        DeterministicReplayComparison,
        ComparisonCorpusDecision,
        DuplicateConformanceFacts,
        ExternalDistributionFactSet,
    )
    nested = (
        ReplayIdentityFacts,
        PostResultDuplicateRequest,
        DuplicateComparisonRequest,
        NearDuplicateRequest,
        NearDuplicateDecision,
        ExternalDistributionFactRequest,
        ExternalFactAvailability,
        ExternalDistributionFactDecision,
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


def test_external_availability_is_closed_redacted_and_nested_canonical() -> None:
    bound = ExternalFactAvailability(
        availability=ExternalFactAvailabilityKind.BOUND,
        fact_kind=ExternalDistributionFactKind.MARGINAL,
        statistics_objective_ref=None,
        fact_ref=_owner("evidence_artifact", "marginal_fact"),
        audit_evidence_ref=_owner("audit_evidence", "marginal_audit"),
        unavailable_reason_ref=None,
    )
    unavailable = ExternalFactAvailability(
        availability=ExternalFactAvailabilityKind.OWNER_UNAVAILABLE,
        fact_kind=None,
        statistics_objective_ref=_owner(
            "statistics_objective",
            "marginal_objective",
        ),
        fact_ref=None,
        audit_evidence_ref=None,
        unavailable_reason_ref=_owner(
            "applicability_reason",
            "statistics_owner_unavailable",
        ),
    )

    assert (
        canonical._nested_from_canonical(
            canonical._nested_to_canonical(bound),
            ExternalFactAvailability,
        )
        == bound
    )
    assert (
        canonical._nested_from_canonical(
            canonical._nested_to_canonical(unavailable),
            ExternalFactAvailability,
        )
        == unavailable
    )
    assert repr(bound) == "ExternalFactAvailability(<protected>)"
    with pytest.raises(TypeError):
        pickle.dumps(bound)
    with pytest.raises(GeneratorValidationError):
        ExternalFactAvailability(
            availability=ExternalFactAvailabilityKind.BOUND,
            fact_kind=ExternalDistributionFactKind.MARGINAL,
            statistics_objective_ref=_owner(
                "statistics_objective",
                "forged_bound_objective",
            ),
            fact_ref=_owner("evidence_artifact", "marginal_fact"),
            audit_evidence_ref=_owner("audit_evidence", "marginal_audit"),
            unavailable_reason_ref=None,
        )


def test_builders_expose_no_caller_boolean_reason_or_count_overrides() -> None:
    conformance_parameters = signature(build_generator_conformance_facts).parameters
    assert tuple(conformance_parameters) == (
        "request",
        "source_event",
        "source_event_ref",
        "outcome_kind",
        "terminal_stage",
        "applicability_stage",
        "payload_facts",
        "support_decision",
        "support_decision_ref",
        "validated_case_facts",
    )
    assert not any(
        "binding" in name or "reason" in name for name in conformance_parameters
    )

    duplicate_parameters = signature(build_duplicate_conformance_facts).parameters
    assert tuple(duplicate_parameters) == (
        "post_result_request",
        "corpus_decision",
        "corpus_decision_ref",
        "near_duplicate_decision",
    )
    assert not any(
        "duplicate" in name and "decision" not in name for name in duplicate_parameters
    )
    assert not {"canonical_case_duplicate", "physical_instance_collision"} & set(
        duplicate_parameters
    )

    assert tuple(signature(build_external_distribution_fact_set).parameters) == (
        "decisions",
    )
    assert not {
        "attempt_count",
        "intended_unit_count",
        "realized_outcome_counts",
    } & set(signature(build_external_distribution_fact_request).parameters)
    assert tuple(signature(build_fixture_replay_probe).parameters) == (
        "baseline_result",
        "baseline_result_ref",
        "baseline_request",
        "replay_authority",
    )
    assert tuple(signature(compare_fixture_replay).parameters) == (
        "baseline_result",
        "baseline_result_ref",
        "probe",
        "probe_ref",
    )
