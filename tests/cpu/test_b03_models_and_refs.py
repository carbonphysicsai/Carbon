"""Focused B-03 foundation model and nominal-ref tests."""

from __future__ import annotations

import pickle
from dataclasses import FrozenInstanceError, fields, replace

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.authoring.model import ApplicabilityBinding, SamplingRole
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.generators.canonical import decode_canonical_bytes, verify_canonical_ref
from carbon.generators.conformance import build_fixture_replay_probe
from carbon.generators.errors import (
    GeneratorCanonicalDecodingError,
    GeneratorInputCode,
    GeneratorReferenceMismatchError,
    GeneratorValidationError,
)
from carbon.generators.model import (
    ApplicabilityReasonKind,
    GeneratorEnvironmentClass,
    GeneratorEnvironmentDescriptor,
    GeneratorOutcomeKind,
    GeneratorRequestIdentity,
    GeneratorTerminalStage,
    RecordRefPair,
)
from carbon.generators.refs import (
    GENERATOR_RUNTIME_REF_TYPES,
    FixtureReplayProbeRef,
    GeneratorEnvironmentRef,
    GeneratorReplayCommitmentRef,
    GeneratorResultRef,
    PendingGenerationAttemptRef,
    decode_generator_ref,
    encode_generator_ref,
    verify_generator_ref,
)
from carbon.generators.service import generate_fixture_case, validate_generator_request
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import SeedDomain


def _challenge() -> ChallengeKey:
    return ChallengeKey("b03_foundation_fixture", "1.0")


def _digest(character: str = "1") -> str:
    return f"sha256:{character * 64}"


def _environment() -> GeneratorEnvironmentDescriptor:
    return GeneratorEnvironmentDescriptor(
        challenge_key=_challenge(),
        environment_id="b03_fixture_environment",
        environment_version="1.0",
        python_implementation="cpython",
        python_version="3.11.16",
        platform_tag="manylinux_2_17_x86_64",
        dependency_lock_digest=_digest(),
        environment_class=GeneratorEnvironmentClass.FIXTURE_ONLY,
    )


def _constructor_bypass(value: object, **changes: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


def test_all_twenty_three_runtime_ref_types_are_distinct_and_round_trip() -> None:
    assert len(GENERATOR_RUNTIME_REF_TYPES) == 23
    assert len(set(GENERATOR_RUNTIME_REF_TYPES)) == 23
    assert len({item.RECORD_TYPE for item in GENERATOR_RUNTIME_REF_TYPES}) == 23

    for index, ref_type in enumerate(GENERATOR_RUNTIME_REF_TYPES, start=1):
        ref = ref_type(_challenge(), _digest(f"{index % 10}"))
        assert decode_generator_ref(encode_generator_ref(ref), ref_type) == ref
        assert repr(ref) == f"{ref_type.__name__}(<protected>)"
        assert str(ref) == repr(ref)
        with pytest.raises(TypeError):
            pickle.dumps(ref)


def test_environment_is_immutable_challenge_bound_and_content_addressed() -> None:
    environment = _environment()
    ref = environment.to_ref()

    assert type(ref) is GeneratorEnvironmentRef
    assert ref.challenge_key == environment.challenge_key
    with pytest.raises(FrozenInstanceError):
        environment.platform_tag = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("verifier", (verify_generator_ref, verify_canonical_ref))
def test_ref_verification_rejects_wrong_nominal_class_with_matching_digest(
    verifier,
) -> None:
    environment = _environment()
    expected = environment.to_ref()
    wrong_nominal_ref = GeneratorResultRef(
        environment.challenge_key,
        expected.content_digest,
    )

    with pytest.raises(GeneratorReferenceMismatchError) as caught:
        verifier(environment, wrong_nominal_ref)

    assert caught.value.path == "/ref_type"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    verifier(environment, expected)


@pytest.mark.parametrize("verifier", (verify_generator_ref, verify_canonical_ref))
@pytest.mark.parametrize("malformed_digest", (1, None, "not-a-tagged-digest"))
def test_ref_verification_reconstructs_the_supplied_correct_nominal_ref(
    verifier,
    malformed_digest: object,
) -> None:
    environment = _environment()
    malformed = _constructor_bypass(
        environment.to_ref(),
        content_digest=malformed_digest,
    )

    with pytest.raises(GeneratorValidationError) as caught:
        verifier(environment, malformed)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == "/content_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("verifier", (verify_generator_ref, verify_canonical_ref))
def test_ref_verification_rejects_cross_challenge_same_digest(
    verifier,
) -> None:
    environment = _environment()
    expected = environment.to_ref()
    wrong_scope = GeneratorEnvironmentRef(
        ChallengeKey("other_b03_foundation_fixture", "1.0"),
        expected.content_digest,
    )

    with pytest.raises(GeneratorReferenceMismatchError) as caught:
        verifier(environment, wrong_scope)

    assert caught.value.path == "/challenge_key"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_record_ref_pair_reconstructs_the_supplied_ref_before_comparison() -> None:
    environment = _environment()
    malformed = _constructor_bypass(
        environment.to_ref(),
        content_digest=None,
    )

    with pytest.raises(GeneratorValidationError) as caught:
        RecordRefPair(environment, malformed)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == "/content_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_record_ref_pair_uses_the_replay_probe_intrinsic_challenge_scope() -> None:
    fixture = make_b03_fixture()
    result = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    ).payload
    probe = build_fixture_replay_probe(
        baseline_result=result,
        baseline_result_ref=result.ref,
        baseline_request=fixture.request,
        replay_authority=fixture.fixture_authority.replay_probe_authority(),
    )

    assert RecordRefPair(probe.record, probe.ref).ref == probe.ref

    wrong_scope = FixtureReplayProbeRef(
        ChallengeKey("other_b03_replay_probe_fixture", "1.0"),
        probe.ref.content_digest,
    )
    with pytest.raises(GeneratorReferenceMismatchError) as caught:
        verify_canonical_ref(probe.record, wrong_scope)
    assert caught.value.path == "/challenge_key"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_outcome_taxonomy_has_exact_contract_order() -> None:
    assert tuple(GeneratorOutcomeKind) == (
        GeneratorOutcomeKind.VALID_GENERATED,
        GeneratorOutcomeKind.REGISTERED_EXCLUSION,
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorOutcomeKind.CENSORED_CASE,
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
    )
    assert "UNKNOWN" not in GeneratorOutcomeKind.__members__
    assert GeneratorTerminalStage.GRAPH_VALIDATION.value == "GRAPH_VALIDATION"


def test_replay_commitment_is_nominal_redacted_and_challenge_bound() -> None:
    key = _challenge()
    issuer = owner_ref(
        "authority_evidence",
        scope_binding=ChallengeScope(key),
        object_id="fixture_replay_issuer",
        object_version="1.0",
        content_digest=_digest("2"),
    )
    replay = GeneratorReplayCommitmentRef(
        key,
        "carbon_generator_fixture_replay",
        "1.0",
        issuer,
        _digest("3"),
    )

    assert repr(replay) == "GeneratorReplayCommitmentRef(<protected>)"
    with pytest.raises(TypeError):
        replay.__reduce__()

    other_key = ChallengeKey("other_fixture", "1.0")
    with pytest.raises(GeneratorValidationError) as caught:
        GeneratorReplayCommitmentRef(
            other_key,
            "carbon_generator_fixture_replay",
            "1.0",
            issuer,
            _digest("3"),
        )
    assert caught.value.code == GeneratorInputCode.CROSS_CHALLENGE.value


def test_boolean_is_rejected_as_uint64_like_attempt_input() -> None:
    from carbon.generators.model import _uint64

    with pytest.raises(GeneratorValidationError):
        _uint64(True, "/attempt_ordinal")


def test_nominal_environment_rejects_an_otherwise_valid_subclass() -> None:
    class EnvironmentSubclass(GeneratorEnvironmentDescriptor):
        pass

    with pytest.raises(GeneratorValidationError) as caught:
        EnvironmentSubclass(
            challenge_key=_challenge(),
            environment_id="b03_fixture_environment",
            environment_version="1.0",
            python_implementation="cpython",
            python_version="3.11.16",
            platform_tag="manylinux_2_17_x86_64",
            dependency_lock_digest=_digest(),
            environment_class=GeneratorEnvironmentClass.FIXTURE_ONLY,
        )

    assert caught.value.code == GeneratorInputCode.WRONG_TYPE.value


def test_ref_validation_does_not_retain_an_internal_exception_chain() -> None:
    with pytest.raises(GeneratorValidationError) as caught:
        GeneratorEnvironmentRef(_challenge(), "not-a-tagged-digest")

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_deeply_reconstructs_replay_commitment() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_replay = _constructor_bypass(
        identity.replay_ref,
        commitment_digest="not-a-tagged-digest",
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(identity, replay_ref=malformed_replay)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == "/commitment_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "field_name",
    (
        "environment_ref",
        "fixture_configuration_ref",
        "intended_unit_link_decision_ref",
    ),
)
def test_request_identity_deeply_reconstructs_direct_runtime_refs(
    field_name: str,
) -> None:
    identity = make_b03_fixture().request.identity()
    malformed = _constructor_bypass(
        getattr(identity, field_name),
        content_digest=None,
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(identity, **{field_name: malformed})

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == "/content_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_deeply_reconstructs_optional_predecessor_ref() -> None:
    identity = make_b03_fixture().request.identity()
    predecessor = PendingGenerationAttemptRef(
        identity.challenge_key,
        _digest("8"),
    )
    successor_identity = replace(
        identity,
        current_attempt_predecessor_ref=predecessor,
        current_attempt_lineage_ref=challenge_owner(
            "protected_replacement_lineage",
            "synthetic_predecessor_lineage",
        ),
    )
    malformed = _constructor_bypass(predecessor, content_digest=1)

    with pytest.raises(GeneratorValidationError) as caught:
        replace(successor_identity, current_attempt_predecessor_ref=malformed)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == "/content_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "field_name",
    (
        "physical_system_ref",
        "candidate_output_ref",
        "primary_population_ref",
        "selection_population_ref",
        "sampling_plan_ref",
    ),
)
def test_request_identity_deeply_reconstructs_direct_authoring_refs(
    field_name: str,
) -> None:
    identity = make_b03_fixture().request.identity()
    malformed = _constructor_bypass(
        getattr(identity, field_name),
        content_digest="not-a-tagged-digest",
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(identity, **{field_name: malformed})

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.path == f"/{field_name}/content_digest"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_reconstructs_nested_role_and_dependency_refs() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_plan = _constructor_bypass(
        identity.role_binding.sampling_plan_ref,
        content_digest="not-a-tagged-digest",
    )
    malformed_role = _constructor_bypass(
        identity.role_binding,
        sampling_plan_ref=malformed_plan,
    )

    with pytest.raises(GeneratorValidationError) as role_error:
        replace(identity, role_binding=malformed_role)
    assert role_error.value.path == "/role_binding/sampling_plan_ref/content_digest"
    assert role_error.value.__cause__ is None
    assert role_error.value.__context__ is None

    malformed_dependency = _constructor_bypass(
        identity.dependency_refs[0],
        content_digest="not-a-tagged-digest",
    )
    with pytest.raises(GeneratorValidationError) as dependency_error:
        replace(
            identity,
            dependency_refs=(malformed_dependency, *identity.dependency_refs[1:]),
        )
    assert dependency_error.value.path == "/dependency_refs/0/content_digest"
    assert dependency_error.value.__cause__ is None
    assert dependency_error.value.__context__ is None


def test_request_identity_deeply_rebuilds_loaded_dependency_identity() -> None:
    identity = make_b03_fixture().request.identity()
    loaded = identity.loaded_dependencies[0]
    malformed_ref = _constructor_bypass(
        loaded.expected_ref,
        content_digest="not-a-tagged-digest",
    )
    malformed_loaded = _constructor_bypass(
        loaded,
        expected_ref=malformed_ref,
        recomputed_ref=malformed_ref,
    )

    with pytest.raises(GeneratorValidationError) as ref_error:
        replace(
            identity,
            loaded_dependencies=(malformed_loaded, *identity.loaded_dependencies[1:]),
        )
    assert ref_error.value.path == "/expected_ref/content_digest"
    assert ref_error.value.__cause__ is None
    assert ref_error.value.__context__ is None

    malformed_qualification = _constructor_bypass(
        loaded.qualification_evidence,
        tag="NOT_APPLICABLE",
    )
    qualification_loaded = _constructor_bypass(
        loaded,
        qualification_evidence=malformed_qualification,
    )
    with pytest.raises(GeneratorValidationError) as qualification_error:
        replace(
            identity,
            loaded_dependencies=(
                qualification_loaded,
                *identity.loaded_dependencies[1:],
            ),
        )
    assert qualification_error.value.path == "/qualification_evidence/tag"
    assert qualification_error.value.__cause__ is None
    assert qualification_error.value.__context__ is None


def test_request_identity_requires_exact_ordered_loaded_dependency_refs() -> None:
    identity = make_b03_fixture().request.identity()
    loaded = identity.loaded_dependencies[0]
    unrelated_ref = replace(
        loaded.expected_ref,
        object_id="unrelated_loaded_dependency",
    )
    unrelated_loaded = replace(
        loaded,
        expected_ref=unrelated_ref,
        recomputed_ref=unrelated_ref,
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(
            identity,
            loaded_dependencies=(unrelated_loaded, *identity.loaded_dependencies[1:]),
        )

    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value
    assert caught.value.path == "/loaded_dependencies"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_deeply_rebuilds_immediate_nested_records() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_values = (
        (
            "attempt_accounting_fallback",
            _constructor_bypass(
                identity.attempt_accounting_fallback,
                authority_failure_ref=challenge_owner(
                    "applicability_reason",
                    "wrong_accounting_fallback_kind",
                ),
            ),
        ),
        (
            "case_construction",
            _constructor_bypass(
                identity.case_construction,
                object_id="not canonical text",
            ),
        ),
        (
            "fixture_loading",
            _constructor_bypass(
                identity.fixture_loading,
                audit_evidence_refs=(),
            ),
        ),
        (
            "disposition_construction",
            _constructor_bypass(
                identity.disposition_construction,
                policy_authority_ref=challenge_owner(
                    "audit_evidence",
                    "wrong_disposition_authority_kind",
                ),
            ),
        ),
    )

    for field_name, malformed in malformed_values:
        with pytest.raises(GeneratorValidationError) as caught:
            replace(identity, **{field_name: malformed})
        assert caught.value.code in {
            GeneratorInputCode.INVALID_VALUE.value,
            GeneratorInputCode.WRONG_TYPE.value,
        }
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None


def test_request_identity_rebuilds_nested_evidence_and_disclosure_values() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_population = _constructor_bypass(
        identity.primary_population_ref,
        content_digest="not-a-tagged-digest",
    )
    malformed_scope = _constructor_bypass(
        identity.disposition_construction.evidence_scope,
        query_population_binding=ApplicabilityBinding.bound(malformed_population),
    )
    malformed_disposition = _constructor_bypass(
        identity.disposition_construction,
        evidence_scope=malformed_scope,
    )
    with pytest.raises(GeneratorValidationError) as scope_error:
        replace(identity, disposition_construction=malformed_disposition)
    assert (
        scope_error.value.path
        == "/evidence_scope/query_population_binding/value/content_digest"
    )
    assert scope_error.value.__cause__ is None
    assert scope_error.value.__context__ is None

    malformed_disclosure = _constructor_bypass(
        identity.case_construction.disclosure_contract,
        release_policy_ref=challenge_owner(
            "aggregation_policy",
            "wrong_release_policy_kind",
        ),
    )
    malformed_case = _constructor_bypass(
        identity.case_construction,
        disclosure_contract=malformed_disclosure,
    )
    with pytest.raises(GeneratorValidationError) as disclosure_error:
        replace(identity, case_construction=malformed_case)
    assert disclosure_error.value.path == "/disclosure_contract/release_policy_ref"
    assert disclosure_error.value.__cause__ is None
    assert disclosure_error.value.__context__ is None


def test_case_construction_requires_nonempty_applicability_bindings() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_case = _constructor_bypass(
        identity.case_construction,
        applicability_bindings=(),
    )

    with pytest.raises(GeneratorValidationError) as direct_error:
        replace(identity.case_construction, applicability_bindings=())
    assert direct_error.value.path == "/applicability_bindings"
    assert direct_error.value.__cause__ is None
    assert direct_error.value.__context__ is None

    with pytest.raises(GeneratorValidationError) as nested_error:
        replace(identity, case_construction=malformed_case)
    assert nested_error.value.path == "/applicability_bindings"
    assert nested_error.value.__cause__ is None
    assert nested_error.value.__context__ is None


def test_request_identity_decoder_rejects_malformed_nested_authoring_ref() -> None:
    identity = make_b03_fixture().request.identity()
    malformed_ref = _constructor_bypass(
        identity.physical_system_ref,
        content_digest="not-a-tagged-digest",
    )
    forged = _constructor_bypass(identity, physical_system_ref=malformed_ref)
    payload = forged.canonical_bytes()

    with pytest.raises(GeneratorCanonicalDecodingError) as caught:
        decode_canonical_bytes(payload, GeneratorRequestIdentity)

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_closed_catalogs_preserve_canonical_round_trip() -> None:
    identity = make_b03_fixture().request.identity()

    assert tuple(
        item.kind
        for item in (
            *identity.attempt_accounting_applicability_reasons,
            *identity.result_applicability_reasons,
        )
    ) == tuple(ApplicabilityReasonKind)
    decoded = decode_canonical_bytes(
        identity.canonical_bytes(),
        GeneratorRequestIdentity,
    )
    assert decoded.canonical_bytes() == identity.canonical_bytes()
    assert decoded.to_ref() == identity.to_ref()


def test_request_identity_requires_exact_accounting_reason_order() -> None:
    identity = make_b03_fixture().request.identity()
    substituted = (
        identity.result_applicability_reasons[0],
        *identity.attempt_accounting_applicability_reasons[1:],
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(identity, attempt_accounting_applicability_reasons=substituted)

    assert caught.value.path == "/attempt_accounting_applicability_reasons"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_requires_exact_result_reason_order() -> None:
    identity = make_b03_fixture().request.identity()
    first, second, *rest = identity.result_applicability_reasons

    with pytest.raises(GeneratorValidationError) as caught:
        replace(
            identity,
            result_applicability_reasons=(second, first, *rest),
        )

    assert caught.value.path == "/result_applicability_reasons"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_rejects_same_length_conformance_substitution() -> None:
    identity = make_b03_fixture().request.identity()
    substituted = replace(
        identity.conformance_fallbacks[0],
        fallback_id="substituted_payload_facts_fallback",
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(
            identity,
            conformance_fallbacks=(substituted, *identity.conformance_fallbacks[1:]),
        )

    assert caught.value.path == "/conformance_fallbacks"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_request_identity_rejects_same_length_failure_catalog_reordering() -> None:
    identity = make_b03_fixture().request.identity()
    first, second, *rest = identity.failure_reason_catalog

    with pytest.raises(GeneratorValidationError) as caught:
        replace(identity, failure_reason_catalog=(second, first, *rest))

    assert caught.value.path == "/failure_reason_catalog"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_distribution_role_mismatch_is_rejected_before_admission() -> None:
    fixture = make_b03_fixture()
    role_binding = replace(
        fixture.request.role_binding,
        sampling_role=SamplingRole.STRESS,
        seed_domain=SeedDomain.OFFICIAL_STRESS,
    )
    link_request = replace(
        fixture.request.intended_unit_link_decision.request,
        role_binding=role_binding,
    )
    link_decision = replace(
        fixture.request.intended_unit_link_decision,
        request=link_request,
    )
    request = replace(
        fixture.request,
        role_binding=role_binding,
        intended_unit_link_decision=link_decision,
        intended_unit_link_decision_ref=link_decision.to_ref(),
    )

    with pytest.raises(GeneratorValidationError) as caught:
        validate_generator_request(
            request,
            fixture_authority=fixture.fixture_authority,
            support_authority=fixture.support_authority,
            censoring_authority=fixture.censoring_authority,
            accounting_authority=fixture.accounting_authority,
        )

    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value
    assert caught.value.path == "/authoring_bundle"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    fixture.fixture_authority.require_available(fixture.request.replay_ref)


def test_same_challenge_sampling_plan_mismatch_is_rejected_before_admission() -> None:
    fixture = make_b03_fixture()
    mismatched_plan_ref = replace(
        fixture.request.authoring_bundle.sampling_plan_ref,
        object_id="other_fixture_sampling_plan",
    )
    role_binding = replace(
        fixture.request.role_binding,
        sampling_plan_ref=mismatched_plan_ref,
    )
    request = replace(fixture.request, role_binding=role_binding)

    with pytest.raises(GeneratorValidationError) as caught:
        validate_generator_request(
            request,
            fixture_authority=fixture.fixture_authority,
            support_authority=fixture.support_authority,
            censoring_authority=fixture.censoring_authority,
            accounting_authority=fixture.accounting_authority,
        )

    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value
    assert caught.value.path == "/role_binding/sampling_plan_ref"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    fixture.fixture_authority.require_available(fixture.request.replay_ref)
