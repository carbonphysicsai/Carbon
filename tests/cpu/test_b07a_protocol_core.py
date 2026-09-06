"""Executable conformance tests for the B-07A shared v2 protocol core."""

from __future__ import annotations

import dataclasses
import math

import pytest
from b07a_fixtures import digest, discovery_resources, strategy

from carbon import research
from carbon.authoring.refs import PhysicalSystemSpecRef
from carbon.fees import StrategyHash
from carbon.registry import ChallengeKey
from carbon.research.canonical import CanonicalWireError


def test_ratified_identity_and_operation_vocabulary_are_exact() -> None:
    assert research.RESEARCH_NAMESPACE == "carbon_research_v2"
    assert research.OFFICIAL_V1_NAMESPACE == "carbon_protocol_v1"
    assert research.SUPPORTED_OPERATIONS == tuple(
        operation.value for operation in research.ResearchOperation
    )
    assert research.SUPPORTED_OPERATIONS == (
        "get_challenge_info",
        "get_interaction_manifest",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "compile_strategy",
        "inspect_prior_alignment",
        "inspect_resources",
        "forecast_resources",
        "start_research_task",
        "get_research_result",
        "cancel_research_task",
    )
    assert not hasattr(research, "ChallengeInteractionManifest")


def test_shared_domain_types_are_imported_not_redefined() -> None:
    assert research.ChallengeKey is ChallengeKey
    assert research.StrategyHash is StrategyHash
    assert research.PhysicalSystemSpecRef is PhysicalSystemSpecRef
    assert research.TrainingStrategy == dict[str, object]


def test_ref_and_resource_field_orders_match_the_wire_contract() -> None:
    assert tuple(
        field.name for field in dataclasses.fields(research.ChallengeInfoRef)
    ) == (
        "challenge_key",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    )
    assert tuple(
        field.name for field in dataclasses.fields(research.ChallengeInfo)
    ) == (
        "schema_version",
        "challenge_key",
        "challenge_version",
        "physical_system_ref",
        "candidate_output_ref",
        "instance_distribution_ref",
        "sampling_plan_ref",
        "training_support_ref",
        "measurement_contract_ref",
        "public_score_policy_ref",
        "disclosure_class",
    )
    assert tuple(
        field.name for field in dataclasses.fields(research.InteractionManifest)
    )[-3:] == (
        "supported_operations",
        "limits",
        "capability_labels",
    )


@pytest.mark.parametrize(
    "factory",
    (
        lambda: type("ChallengeInfoRefChild", (research.ChallengeInfoRef,), {})(
            ChallengeKey("b07a_fixture", "1.0"), content_digest=digest()
        ),
        lambda: type("ChallengeInfoChild", (research.ChallengeInfo,), {})(
            *dataclasses.astuple(discovery_resources()[0])
        ),
        lambda: research.GetChallengeInfoRequest(
            type("ChallengeKeyChild", (ChallengeKey,), {})("b07a_fixture", "1.0")
        ),
    ),
)
def test_nominal_subclasses_are_rejected(factory) -> None:
    with pytest.raises(TypeError):
        factory()


def test_resources_calls_and_replies_round_trip_canonically() -> None:
    info, manifest = discovery_resources()
    values = (
        info,
        manifest,
        research.ServiceCall(
            research.RESEARCH_NAMESPACE,
            "get_challenge_info",
            research.GetChallengeInfoRequest(info.challenge_key),
        ),
        research.ServiceReply(research.ReplyStatus.OK, info),
        research.ServiceReply(
            research.ReplyStatus.ERROR,
            research.public_error(research.ResearchServiceErrorCode.INTERNAL_FAILURE),
        ),
    )
    for value in values:
        encoded = research.canonical_bytes(value)
        decoded = research.load_canonical(encoded, type(value))
        assert decoded == value
        assert research.canonical_bytes(decoded) == encoded


def test_content_hash_is_stable_and_binds_exact_resource_bytes() -> None:
    info, _ = discovery_resources()
    repeated, _ = discovery_resources()
    changed, _ = discovery_resources("2.0")
    assert info.to_ref() == repeated.to_ref()
    assert info.to_ref() != changed.to_ref()
    assert research.canonical_digest(info) == info.to_ref().content_digest


@pytest.mark.parametrize("suffix", (b"\x00", b"garbage"))
def test_trailing_representations_are_rejected(suffix: bytes) -> None:
    info, _ = discovery_resources()
    with pytest.raises(CanonicalWireError) as failure:
        research.load_canonical(research.canonical_bytes(info) + suffix, type(info))
    assert (
        failure.value.code
        is research.ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
    )


def test_call_and_resource_byte_limits_reject_before_parsing() -> None:
    for expected, limit in (
        (research.ServiceCall, research.MAX_CALL_REPLY_BYTES),
        (research.ChallengeInfo, research.MAX_RESOURCE_BYTES),
    ):
        with pytest.raises(CanonicalWireError) as failure:
            research.load_canonical(b"x" * (limit + 1), expected)
        assert failure.value.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED


def test_error_message_path_and_detail_bounds_include_boundary() -> None:
    code = research.ResearchServiceErrorCode.INTERNAL_FAILURE
    retry = research.RetryDisposition.NEVER
    research.ResearchServiceError(code, ("p",) * 32, "x" * 1_024, retry, ())
    with pytest.raises(ValueError):
        research.ResearchServiceError(code, ("p",) * 33, "safe", retry, ())
    with pytest.raises(ValueError):
        research.ResearchServiceError(code, (), "x" * 1_025, retry, ())
    with pytest.raises(ValueError):
        research.ResearchServiceError(
            code,
            (),
            "safe",
            retry,
            tuple(research.ErrorDetail(f"k{i}", "v") for i in range(33)),
        )


def test_unknown_and_duplicate_fields_are_rejected() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(key),
    )
    encoded = research.canonical_bytes(call)
    unknown = encoded.replace(b"namespace", b"namespacx", 1)
    with pytest.raises(CanonicalWireError) as failure:
        research.load_canonical(unknown, research.ServiceCall)
    assert failure.value.code is research.ResearchServiceErrorCode.UNKNOWN_FIELD
    duplicate = encoded.replace(b"operation", b"namespace", 1)
    with pytest.raises(CanonicalWireError) as failure:
        research.load_canonical(duplicate, research.ServiceCall)
    assert (
        failure.value.code
        is research.ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
    )


@pytest.mark.parametrize("bad", (True, False, -1, 2**64))
def test_uint64_rejects_booleans_negative_and_overflow(bad: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        research.ProtocolLimit("test_limit", bad)


@pytest.mark.parametrize("bad", (math.nan, math.inf, -math.inf, 1, True))
def test_float_fields_reject_nonfinite_and_nonfloat_values(bad: object) -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    from carbon.resource_policy.refs import (
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        ResourceClassRef,
    )

    ref = ResourceClassRef(
        key,
        "cpu",
        "1.0",
        "1.0",
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        digest(),
    )
    with pytest.raises((TypeError, ValueError)):
        research.ResourceLineItem(ref, bad, "seconds", (0.0, 1.0))


def test_strategy_collection_and_depth_boundaries_are_exact() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    research.DryValidateRequest(key, strategy(parameters={"items": [0] * 4_096}))
    with pytest.raises(ValueError):
        research.DryValidateRequest(key, strategy(parameters={"items": [0] * 4_097}))

    within: object = 0
    for _ in range(29):
        within = [within]
    research.DryValidateRequest(key, strategy(parameters={"nested": within}))
    outside = [[within]]
    with pytest.raises(ValueError):
        research.DryValidateRequest(key, strategy(parameters={"nested": outside}))


def test_forbidden_controls_are_rejected_at_every_strategy_depth() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    for field in ("Official_Seed", "Execution-Context", "truth", "P"):
        with pytest.raises(ValueError):
            research.DryValidateRequest(
                key,
                strategy(parameters={"nested": [{field: "protected"}]}),
            )


def test_manifest_enforces_order_bounds_and_unavailable_slots() -> None:
    _, manifest = discovery_resources()
    assert manifest.prior_availability == research.NoPriorAvailability()
    assert manifest.practice_scope_ref is None
    assert manifest.practice_pack_refs == ()
    assert manifest.scaffold_catalog_ref is None
    assert manifest.capability_labels == ()
    with pytest.raises(ValueError):
        dataclasses.replace(
            manifest,
            supported_operations=tuple(reversed(research.SUPPORTED_OPERATIONS)),
        )
    with pytest.raises(ValueError):
        dataclasses.replace(manifest, limits=manifest.limits[:-1])


def test_wrong_challenge_refs_and_conflicting_resources_reject() -> None:
    info, manifest = discovery_resources()
    other, _ = discovery_resources(challenge_id="other_fixture")
    with pytest.raises(ValueError):
        dataclasses.replace(info, physical_system_ref=other.physical_system_ref)
    with pytest.raises(ValueError):
        research.DiscoveryResourceVersion(
            info,
            dataclasses.replace(
                manifest,
                challenge_info_ref=research.ChallengeInfoRef(
                    manifest.challenge_key,
                    content_digest=digest("f"),
                ),
            ),
        )
    with pytest.raises(ValueError):
        research.CompileStrategyRequest(
            info.challenge_key,
            strategy(),
            other.training_support_ref,
        )


def test_exact_token_and_operation_numeric_boundaries() -> None:
    info, manifest = discovery_resources()
    research.ForecastResourcesRequest(
        info.challenge_key,
        strategy(),
        manifest.resource_policy_ref,
        1,
    )
    research.ForecastResourcesRequest(
        info.challenge_key,
        strategy(),
        manifest.resource_policy_ref,
        604_800,
    )
    for value in (0, 604_801, True):
        with pytest.raises((TypeError, ValueError)):
            research.ForecastResourcesRequest(
                info.challenge_key,
                strategy(),
                manifest.resource_policy_ref,
                value,
            )


def test_prior_channel_and_task_kind_are_closed_nominal_enums() -> None:
    info, _ = discovery_resources()
    research.ActivePriorSelector(research.PriorChannel.PUBLIC)
    with pytest.raises(TypeError):
        research.ActivePriorSelector("PUBLIC")
    assert tuple(kind.value for kind in research.ResearchTaskKind) == (
        "RECONSTRUCTION_REHEARSAL",
        "PRACTICE",
        "PAIRED_PRACTICE",
        "RESOURCE_CALIBRATION",
    )
    with pytest.raises((TypeError, ValueError)):
        research.PriorChannelRef(
            info.challenge_key,
            "PUBLIC",
            content_digest=digest(),
        )


def test_shared_prior_pack_is_exact_and_canonically_round_trips() -> None:
    info, manifest = discovery_resources()
    pack = research.PriorPack(
        research.RESEARCH_SCHEMA_VERSION,
        research.RESEARCH_CANONICALIZATION_PROFILE,
        info.challenge_key,
        "fixture_prior",
        "1.0",
        research.PriorChannel.TEST_ONLY_FIXTURE,
        0,
        research.PriorPublicationClass.TEST_ONLY,
        10,
        10,
        10,
        manifest.to_ref(),
        manifest.parameter_catalog_ref,
        research.PriorPolicyBundleRef(info.challenge_key, content_digest=digest("b")),
        "fixture_builder",
        None,
        (),
        manifest.disclosure_policy_ref,
        ("TEST_ONLY",),
    )
    encoded = research.canonical_bytes(pack)
    assert research.load_canonical(encoded, research.PriorPack) == pack
    with pytest.raises(ValueError):
        dataclasses.replace(
            pack,
            channel=research.PriorChannel.PUBLIC,
        )
