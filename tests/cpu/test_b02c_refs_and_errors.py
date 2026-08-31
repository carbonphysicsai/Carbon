"""Exact B-02C error and nominal-reference conformance tests."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from carbon import resource_policy
from carbon.authoring.canonical import tagged_sha256
from carbon.registry import ChallengeKey
from carbon.resource_policy import refs as resource_policy_refs
from carbon.resource_policy.errors import (
    INPUT_REJECTION_MESSAGES,
    ResourcePolicyCanonicalDecodingError,
    ResourcePolicyInputCode,
    ResourcePolicyInputRejected,
    ResourcePolicyReferenceMismatchError,
)
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    FixtureResourceDecisionRef,
    ObservedResourceReceiptRef,
    ResearchResourcePolicyRef,
    ResourceCancellationRecordRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
    decode_resource_policy_ref,
    encode_resource_policy_ref,
    verify_resource_policy_ref,
)

_KEY = ChallengeKey("fixture_resource_policy", "1.0")
_OTHER_KEY = ChallengeKey("other_resource_policy", "1.0")
_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64


def _field_names(value_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(value_type))


def _authored(ref_type: type, *, key: ChallengeKey = _KEY) -> object:
    return ref_type(
        key,
        "fixture_object",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _resolved(ref_type: type, *, key: ChallengeKey = _KEY) -> object:
    return ref_type(
        key,
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def test_input_rejection_registry_is_closed_fixed_and_non_echoing() -> None:
    assert tuple(ResourcePolicyInputCode) == (
        ResourcePolicyInputCode.WRONG_TYPE,
        ResourcePolicyInputCode.INVALID_VALUE,
        ResourcePolicyInputCode.INVALID_CANONICAL_BYTES,
        ResourcePolicyInputCode.TRAILING_BYTES,
        ResourcePolicyInputCode.REF_DIGEST_MISMATCH,
        ResourcePolicyInputCode.POLICY_BUNDLE_INCOMPLETE,
        ResourcePolicyInputCode.LIMIT_NOT_BOUND,
    )
    assert set(INPUT_REJECTION_MESSAGES) == set(ResourcePolicyInputCode)

    hostile = "attacker-secret-path-7f018"
    error = ResourcePolicyInputRejected(
        ResourcePolicyInputCode.INVALID_VALUE,
        path=f"/trusted/{hostile}",
    )
    assert error.code == "INVALID_VALUE"
    assert str(error) == "input value is outside the closed contract"
    assert hostile not in str(error)


def test_ref_field_order_and_nominal_types_are_exact() -> None:
    authored_fields = (
        "challenge_key",
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    )
    resolved_fields = (
        "challenge_key",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    )
    assert _field_names(ResourceClassRef) == authored_fields
    assert _field_names(ResearchResourcePolicyRef) == authored_fields
    assert _field_names(StaticResourceAssessmentRef) == resolved_fields
    assert _field_names(FixtureResourceDecisionRef) == resolved_fields
    assert _field_names(ResourceCancellationRecordRef) == resolved_fields
    assert _field_names(ObservedResourceReceiptRef) == resolved_fields

    refs = (
        _authored(ResourceClassRef),
        _authored(ResearchResourcePolicyRef),
        _resolved(StaticResourceAssessmentRef),
        _resolved(FixtureResourceDecisionRef),
        _resolved(ResourceCancellationRecordRef),
        _resolved(ObservedResourceReceiptRef),
    )
    assert len({type(item) for item in refs}) == len(refs)
    assert all(item.challenge_key == _KEY for item in refs)


def test_generic_ref_maker_is_not_a_public_issuance_bypass() -> None:
    assert "make_resource_policy_ref" not in resource_policy_refs.__all__
    assert "make_resource_policy_ref" not in resource_policy.__all__


@pytest.mark.parametrize(
    "ref",
    (
        _authored(ResourceClassRef),
        _authored(ResearchResourcePolicyRef),
        _resolved(StaticResourceAssessmentRef),
        _resolved(FixtureResourceDecisionRef),
        _resolved(ResourceCancellationRecordRef),
        _resolved(ObservedResourceReceiptRef),
    ),
)
def test_all_ref_types_round_trip_and_reject_trailing_bytes(ref: object) -> None:
    payload = encode_resource_policy_ref(ref)

    assert decode_resource_policy_ref(payload, expected_type=type(ref)) == ref
    with pytest.raises(ResourcePolicyCanonicalDecodingError) as caught:
        decode_resource_policy_ref(payload + b"\x00", expected_type=type(ref))
    assert caught.value.code == "TRAILING_BYTES"


def test_ref_decoder_rejects_same_shape_nominal_substitution() -> None:
    class_ref = _authored(ResourceClassRef)
    payload = encode_resource_policy_ref(class_ref)

    with pytest.raises(ResourcePolicyCanonicalDecodingError):
        decode_resource_policy_ref(
            payload,
            expected_type=ResearchResourcePolicyRef,
        )
    assert type(class_ref) is not ResearchResourcePolicyRef


def test_ref_verification_rejects_digest_tamper_and_cross_challenge_binding() -> None:
    canonical_bytes = b"fixture-resource-policy-document"
    exact = ResourceClassRef(
        _KEY,
        "fixture_class",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        tagged_sha256(canonical_bytes),
    )
    assert (
        verify_resource_policy_ref(
            exact,
            canonical_bytes=canonical_bytes,
            challenge_key=_KEY,
            object_id="fixture_class",
            object_version="1.0",
        )
        == exact
    )

    with pytest.raises(ResourcePolicyReferenceMismatchError):
        verify_resource_policy_ref(
            replace(exact, content_digest=_OTHER_DIGEST),
            canonical_bytes=canonical_bytes,
            challenge_key=_KEY,
            object_id="fixture_class",
            object_version="1.0",
        )
    with pytest.raises(ResourcePolicyReferenceMismatchError):
        verify_resource_policy_ref(
            exact,
            canonical_bytes=canonical_bytes,
            challenge_key=_OTHER_KEY,
            object_id="fixture_class",
            object_version="1.0",
        )


def test_refs_reject_subclasses_and_bool_or_shape_confusion() -> None:
    class ResourceClassRefSubclass(ResourceClassRef):
        pass

    with pytest.raises(ResourcePolicyInputRejected) as subclass_error:
        ResourceClassRefSubclass(
            _KEY,
            "fixture_class",
            "1.0",
            RESOURCE_POLICY_SCHEMA_VERSION,
            RESOURCE_POLICY_CANONICALIZATION_PROFILE,
            _DIGEST,
        )
    assert subclass_error.value.code == "WRONG_TYPE"

    with pytest.raises(ResourcePolicyInputRejected):
        ResourceClassRef(
            _KEY,
            True,
            "1.0",
            RESOURCE_POLICY_SCHEMA_VERSION,
            RESOURCE_POLICY_CANONICALIZATION_PROFILE,
            _DIGEST,
        )
