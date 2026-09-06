"""Positive and hostile-provider tests for bounded B-07A discovery."""

from __future__ import annotations

import dataclasses

from b07a_fixtures import discovery_resources

from carbon import research
from carbon.registry import ChallengeKey


def _adapter(*versions: str) -> research.LocalDiscoveryAdapter:
    resources = tuple(
        research.DiscoveryResourceVersion(*discovery_resources(version))
        for version in versions
    )
    provider = research.InMemoryDiscoveryProvider(resources)
    return research.LocalDiscoveryAdapter(provider, provider)


def _call(adapter, operation: str, request, namespace=research.RESEARCH_NAMESPACE):
    return adapter.call(research.ServiceCall(namespace, operation, request))


def test_positive_discovery_returns_exact_resources() -> None:
    info, manifest = discovery_resources()
    adapter = _adapter("1.0")
    info_reply = _call(
        adapter,
        "get_challenge_info",
        research.GetChallengeInfoRequest(info.challenge_key),
    )
    manifest_reply = _call(
        adapter,
        "get_interaction_manifest",
        research.GetInteractionManifestRequest(info.challenge_key),
    )
    assert info_reply == research.ServiceReply(research.ReplyStatus.OK, info)
    assert manifest_reply == research.ServiceReply(research.ReplyStatus.OK, manifest)


def test_historical_retrieval_never_redirects_to_latest() -> None:
    adapter = _adapter("1.0", "2.0")
    old = _call(
        adapter,
        "get_challenge_info",
        research.GetChallengeInfoRequest(ChallengeKey("b07a_fixture", "1.0")),
    )
    new = _call(
        adapter,
        "get_challenge_info",
        research.GetChallengeInfoRequest(ChallengeKey("b07a_fixture", "2.0")),
    )
    assert old.status is research.ReplyStatus.OK
    assert new.status is research.ReplyStatus.OK
    assert old.result.challenge_version == "1.0"
    assert new.result.challenge_version == "2.0"
    assert old.result.to_ref() != new.result.to_ref()


def test_absent_exact_version_is_challenge_not_found() -> None:
    adapter = _adapter("2.0")
    reply = _call(
        adapter,
        "get_challenge_info",
        research.GetChallengeInfoRequest(ChallengeKey("b07a_fixture", "1.0")),
    )
    assert reply.status is research.ReplyStatus.ERROR
    assert reply.result.code is research.ResearchServiceErrorCode.CHALLENGE_NOT_FOUND


def test_namespace_operation_and_capability_precedence() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    adapter = _adapter("1.0")
    wrong_namespace = _call(
        adapter,
        "unknown",
        research.GetChallengeInfoRequest(key),
        "merged_service",
    )
    official = _call(
        adapter,
        "submit",
        research.GetChallengeInfoRequest(key),
    )
    unknown = _call(
        adapter,
        "unknown",
        research.GetChallengeInfoRequest(key),
    )
    unavailable = _call(
        adapter,
        "get_prior",
        research.GetPriorRequest(key, research.NoPriorSelector()),
    )
    assert (
        wrong_namespace.result.code
        is research.ResearchServiceErrorCode.NAMESPACE_MISMATCH
    )
    assert official.result.code is research.ResearchServiceErrorCode.NAMESPACE_MISMATCH
    assert (
        unknown.result.code is research.ResearchServiceErrorCode.OPERATION_UNSUPPORTED
    )
    assert (
        unavailable.result.code
        is research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
    )


def test_request_lookalike_and_cross_operation_type_reject() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    adapter = _adapter("1.0")
    call = object.__new__(research.ServiceCall)
    object.__setattr__(call, "namespace", research.RESEARCH_NAMESPACE)
    object.__setattr__(call, "operation", "get_challenge_info")
    object.__setattr__(call, "request", research.GetInteractionManifestRequest(key))
    reply = adapter.call(call)
    assert reply.result.code is research.ResearchServiceErrorCode.REQUEST_TYPE_INVALID


def test_call_bytes_returns_stable_error_without_partial_output() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    adapter = _adapter("1.0")
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(key),
    )
    payload = adapter.call_bytes(research.canonical_bytes(call) + b"secret")
    reply = research.load_canonical(payload, research.ServiceReply)
    assert reply.status is research.ReplyStatus.ERROR
    assert (
        reply.result.code
        is research.ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
    )
    assert "secret" not in reply.result.message


class _HostileProvider:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def get_challenge_info(self, challenge_key):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def get_interaction_manifest(self, challenge_key):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_hostile_provider_type_and_exception_text_are_not_disclosed() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    for outcome, expected in (
        (
            {"official_seed": "do-not-leak"},
            research.ResearchServiceErrorCode.DISCLOSURE_REJECTED,
        ),
        (
            RuntimeError("private evaluator topology"),
            research.ResearchServiceErrorCode.INTERNAL_FAILURE,
        ),
    ):
        provider = _HostileProvider(outcome)
        adapter = research.LocalDiscoveryAdapter(provider, provider)
        reply = _call(
            adapter,
            "get_challenge_info",
            research.GetChallengeInfoRequest(key),
        )
        assert reply.status is research.ReplyStatus.ERROR
        assert reply.result.code is expected
        assert "seed" not in reply.result.message.casefold()
        assert "topology" not in reply.result.message.casefold()


def test_hostile_mutated_manifest_is_rejected_without_partial_result() -> None:
    info, manifest = discovery_resources()
    object.__setattr__(
        manifest,
        "challenge_info_ref",
        info.to_ref().__class__(
            info.challenge_key,
            content_digest="sha256:" + "f" * 64,
        ),
    )
    provider = _HostileProvider(manifest)
    catalog = _HostileProvider(info)
    adapter = research.LocalDiscoveryAdapter(catalog, provider)
    reply = _call(
        adapter,
        "get_interaction_manifest",
        research.GetInteractionManifestRequest(info.challenge_key),
    )
    assert reply.status is research.ReplyStatus.ERROR
    assert reply.result.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH


def test_provider_unavailable_maps_to_same_request_retry() -> None:
    key = ChallengeKey("b07a_fixture", "1.0")
    provider = _HostileProvider(research.DiscoveryProviderUnavailable())
    reply = _call(
        research.LocalDiscoveryAdapter(provider, provider),
        "get_challenge_info",
        research.GetChallengeInfoRequest(key),
    )
    assert reply.result.code is research.ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
    assert reply.result.retry_disposition is research.RetryDisposition.SAME_REQUEST


def test_provider_catalog_rejects_duplicate_and_conflicting_versions() -> None:
    info, manifest = discovery_resources()
    resource = research.DiscoveryResourceVersion(info, manifest)
    try:
        research.InMemoryDiscoveryProvider((resource, resource))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate exact Challenge version was accepted")
    other, _ = discovery_resources(challenge_id="other_fixture")
    try:
        research.DiscoveryResourceVersion(
            info,
            dataclasses.replace(
                manifest, physical_system_ref=other.physical_system_ref
            ),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("cross-Challenge resource was accepted")
