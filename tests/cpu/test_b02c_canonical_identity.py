"""Domain-separated canonical identity and object-specific ref tests for B-02C."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path

import pytest
from b02c_fixtures import availability, make_resource_policy_fixture

from carbon.authoring.canonical import tagged_sha256
from carbon.resource_policy import canonical
from carbon.resource_policy.canonical import (
    MODEL_CANONICAL_FIELD_REGISTRY_V1,
    decode_fixture_resource_availability,
    decode_fixture_resource_decision,
    decode_research_resource_policy,
    decode_resource_class,
    decode_resource_enforcement_event,
    decode_resource_enforcement_result,
    decode_static_resource_assessment,
    encode_fixture_resource_availability,
    encode_fixture_resource_decision,
    encode_research_resource_policy,
    encode_resource_class,
    encode_resource_enforcement_event,
    encode_resource_enforcement_result,
    encode_static_resource_assessment,
    fixture_resource_decision_to_ref,
    research_resource_policy_to_ref,
    resource_class_to_ref,
    static_resource_assessment_to_ref,
    verify_fixture_resource_decision_ref,
    verify_research_resource_policy_ref,
    verify_resource_class_ref,
    verify_static_resource_assessment_ref,
)
from carbon.resource_policy.errors import (
    ResourcePolicyCanonicalDecodingError,
    ResourcePolicyInputRejected,
    ResourcePolicyReferenceMismatchError,
)
from carbon.resource_policy.model import (
    EnforcementObservationKind,
    FixtureResourceAvailability,
    FixtureResourceDecision,
    ObservedResourceQuantity,
    ResearchResourcePolicy,
    ResourceClass,
    ResourceEnforcementObservation,
    ResourceEnforcementResult,
    ResourceObservationRole,
    StaticResourceAssessment,
)
from carbon.resource_policy.service import (
    assess_static_resources,
    decide_fixture_readiness,
    evaluate_enforcement,
)

_OTHER_DIGEST = "sha256:" + "9" * 64


def _derived_values(tmp_path: Path) -> tuple[object, ...]:
    fixture = make_resource_policy_fixture(tmp_path)
    assessment = assess_static_resources(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        expected_active_policy_ref=fixture.policy_ref,
        expected_active_resource_class_ref=fixture.resource_class_ref,
        authority_context=fixture.context,
    )
    assessment_ref = static_resource_assessment_to_ref(assessment)
    available = availability(fixture)
    decision = decide_fixture_readiness(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        availability_input=available,
    )
    decision_ref = fixture_resource_decision_to_ref(decision)
    unit = fixture.plan.static_resource_requirements[0].unit_ref
    result = evaluate_enforcement(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        decision=decision,
        decision_ref=decision_ref,
        limit_id="runtime_limit",
        observation=ResourceEnforcementObservation(
            ObservedResourceQuantity(
                "consumed_units",
                unit,
                20,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
            EnforcementObservationKind.CURRENT_TOTAL,
        ),
    )
    return fixture, assessment, available, decision, result


def test_class_and_policy_round_trip_with_exact_object_specific_refs(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    class_payload = encode_resource_class(fixture.resource_class)
    policy_payload = encode_research_resource_policy(fixture.policy)

    assert (
        decode_resource_class(
            class_payload,
            expected_ref=fixture.resource_class_ref,
        )
        == fixture.resource_class
    )
    assert (
        decode_research_resource_policy(
            policy_payload,
            class_bundle=fixture.class_bundle,
            expected_ref=fixture.policy_ref,
        )
        == fixture.policy
    )
    assert resource_class_to_ref(fixture.resource_class).content_digest == (
        tagged_sha256(class_payload)
    )
    assert research_resource_policy_to_ref(
        fixture.policy,
        class_bundle=fixture.class_bundle,
    ).content_digest == tagged_sha256(policy_payload)
    assert (
        verify_resource_class_ref(
            fixture.resource_class_ref,
            value=fixture.resource_class,
        )
        == fixture.resource_class_ref
    )
    assert (
        verify_research_resource_policy_ref(
            fixture.policy_ref,
            value=fixture.policy,
            class_bundle=fixture.class_bundle,
        )
        == fixture.policy_ref
    )


def test_policy_decode_and_ref_issuance_require_the_complete_bundle(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    payload = encode_research_resource_policy(fixture.policy)

    with pytest.raises(TypeError):
        decode_research_resource_policy(payload)  # type: ignore[call-arg]
    with pytest.raises(ResourcePolicyInputRejected) as caught:
        decode_research_resource_policy(payload, class_bundle=())
    assert caught.value.code == "POLICY_BUNDLE_INCOMPLETE"
    with pytest.raises(ResourcePolicyInputRejected):
        research_resource_policy_to_ref(fixture.policy, class_bundle=())


@pytest.mark.parametrize(
    ("encoder", "decoder", "index"),
    (
        (encode_static_resource_assessment, decode_static_resource_assessment, 1),
        (
            encode_fixture_resource_availability,
            decode_fixture_resource_availability,
            2,
        ),
        (encode_fixture_resource_decision, decode_fixture_resource_decision, 3),
        (
            encode_resource_enforcement_result,
            decode_resource_enforcement_result,
            4,
        ),
    ),
)
def test_derived_documents_round_trip_and_reject_trailing_bytes(
    tmp_path: Path,
    encoder: object,
    decoder: object,
    index: int,
) -> None:
    values = _derived_values(tmp_path)
    value = values[index]
    payload = encoder(value)  # type: ignore[operator]

    assert decoder(payload) == value  # type: ignore[operator]
    with pytest.raises(ResourcePolicyCanonicalDecodingError) as caught:
        decoder(payload + b"\x00")  # type: ignore[operator]
    assert caught.value.code == "TRAILING_BYTES"


def test_enforcement_event_is_a_strict_document_but_has_no_nominal_ref(
    tmp_path: Path,
) -> None:
    result = _derived_values(tmp_path)[4]
    assert type(result) is ResourceEnforcementResult
    payload = encode_resource_enforcement_event(result.event)

    assert decode_resource_enforcement_event(payload) == result.event
    assert not hasattr(canonical, "resource_enforcement_event_to_ref")
    assert not hasattr(canonical, "resource_enforcement_result_to_ref")


def test_resolved_ref_issuance_and_verification_are_nominally_separate(
    tmp_path: Path,
) -> None:
    _, assessment, _, decision, _ = _derived_values(tmp_path)
    assessment_ref = static_resource_assessment_to_ref(assessment)
    decision_ref = fixture_resource_decision_to_ref(decision)

    assert type(assessment) is StaticResourceAssessment
    assert type(decision) is FixtureResourceDecision
    assert type(assessment_ref) is not type(decision_ref)
    assert (
        verify_static_resource_assessment_ref(
            assessment_ref,
            value=assessment,
        )
        == assessment_ref
    )
    assert (
        verify_fixture_resource_decision_ref(
            decision_ref,
            value=decision,
        )
        == decision_ref
    )
    with pytest.raises(ResourcePolicyReferenceMismatchError):
        verify_static_resource_assessment_ref(decision_ref, value=assessment)


def test_digest_tamper_stale_expected_ref_and_nominal_decoder_substitution_reject(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    payload = encode_resource_class(fixture.resource_class)

    with pytest.raises(ResourcePolicyReferenceMismatchError):
        decode_resource_class(
            payload,
            expected_ref=replace(
                fixture.resource_class_ref,
                content_digest=_OTHER_DIGEST,
            ),
        )
    with pytest.raises(ResourcePolicyReferenceMismatchError):
        decode_resource_class(payload, expected_ref=fixture.policy_ref)
    with pytest.raises(ResourcePolicyCanonicalDecodingError):
        decode_static_resource_assessment(payload)


def test_set_like_construction_order_cannot_change_class_identity(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    reordered = replace(
        fixture.resource_class,
        observation_metrics=tuple(reversed(fixture.resource_class.observation_metrics)),
        required_plan_environment_pins=tuple(
            reversed(fixture.resource_class.required_plan_environment_pins)
        ),
    )

    assert reordered == fixture.resource_class
    assert encode_resource_class(reordered) == encode_resource_class(
        fixture.resource_class
    )
    assert resource_class_to_ref(reordered) == fixture.resource_class_ref


def test_literal_canonical_field_registry_matches_exact_dataclass_order() -> None:
    expected = {
        "resource_class": tuple(field.name for field in fields(ResourceClass)),
        "research_resource_policy": tuple(
            field.name for field in fields(ResearchResourcePolicy)
        ),
        "static_resource_assessment": tuple(
            field.name for field in fields(StaticResourceAssessment)
        ),
        "fixture_resource_availability": tuple(
            field.name for field in fields(FixtureResourceAvailability)
        ),
        "fixture_resource_decision": tuple(
            field.name for field in fields(FixtureResourceDecision)
        ),
        "resource_enforcement_result": tuple(
            field.name for field in fields(ResourceEnforcementResult)
        ),
    }

    assert all(
        MODEL_CANONICAL_FIELD_REGISTRY_V1[kind] == names
        for kind, names in expected.items()
    )


def test_class_and_policy_identity_are_fresh_process_hash_seed_independent(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    test_support = repository_root / "tests" / "cpu"
    script = """
import json
from pathlib import Path

from b02c_fixtures import make_resource_policy_fixture
from carbon.resource_policy.canonical import (
    encode_research_resource_policy,
    encode_resource_class,
)

fixture = make_resource_policy_fixture(Path.cwd())
print(json.dumps({
    "class_bytes": encode_resource_class(fixture.resource_class).hex(),
    "class_digest": fixture.resource_class_ref.content_digest,
    "policy_bytes": encode_research_resource_policy(fixture.policy).hex(),
    "policy_digest": fixture.policy_ref.content_digest,
}, sort_keys=True))
"""
    outputs = []
    for hash_seed in ("1", "8675309"):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": hash_seed,
            "PYTHONPATH": os.pathsep.join((str(repository_root), str(test_support))),
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(json.loads(result.stdout))

    assert outputs[0] == outputs[1]
