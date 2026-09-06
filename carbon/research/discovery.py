"""Bounded local-only B-07A discovery provider and adapter."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.registry import ChallengeKey

from .canonical import CanonicalWireError, canonical_bytes, load_canonical
from .errors import (
    DiscoveryProviderUnavailable,
    ResearchServiceErrorCode,
    public_error,
)
from .model import (
    OFFICIAL_V1_OPERATIONS,
    RESEARCH_NAMESPACE,
    SUPPORTED_OPERATIONS,
    ChallengeInfo,
    GetChallengeInfoRequest,
    GetInteractionManifestRequest,
    InteractionManifest,
    NoPriorAvailability,
    ReplyStatus,
    ServiceCall,
    ServiceReply,
)
from .providers import ChallengeCatalogProvider, ManifestProvider


@dataclass(frozen=True, slots=True)
class DiscoveryResourceVersion:
    challenge_info: ChallengeInfo
    interaction_manifest: InteractionManifest

    def __post_init__(self) -> None:
        if type(self) is not DiscoveryResourceVersion:
            raise TypeError("discovery resource subclasses are rejected")
        if type(self.challenge_info) is not ChallengeInfo:
            raise TypeError("challenge_info must use its exact wire type")
        if type(self.interaction_manifest) is not InteractionManifest:
            raise TypeError("manifest must use its exact wire type")
        _validate_pair(self.challenge_info, self.interaction_manifest)


def _validate_pair(info: ChallengeInfo, manifest: InteractionManifest) -> None:
    if info.challenge_key != manifest.challenge_key:
        raise ValueError("discovery resources have different Challenges")
    if manifest.challenge_info_ref != info.to_ref():
        raise ValueError("manifest ChallengeInfoRef does not match canonical bytes")
    pairs = (
        ("physical_system_ref", info.physical_system_ref, manifest.physical_system_ref),
        (
            "candidate_output_ref",
            info.candidate_output_ref,
            manifest.candidate_output_ref,
        ),
        (
            "instance_distribution_ref",
            info.instance_distribution_ref,
            manifest.instance_distribution_ref,
        ),
        ("sampling_plan_ref", info.sampling_plan_ref, manifest.sampling_plan_ref),
        (
            "training_support_ref",
            info.training_support_ref,
            manifest.training_support_ref,
        ),
        (
            "measurement_contract_ref",
            info.measurement_contract_ref,
            manifest.measurement_contract_ref,
        ),
        (
            "public_score_policy_ref",
            info.public_score_policy_ref,
            manifest.public_score_policy_ref,
        ),
    )
    for name, expected, observed in pairs:
        if type(observed) is not type(expected) or observed != expected:
            raise ValueError(f"manifest {name} conflicts with ChallengeInfo")
    if manifest.capability_labels:
        raise ValueError(
            "B-07A public discovery cannot advertise fixture prior authority"
        )
    if type(manifest.prior_availability) is not NoPriorAvailability:
        raise ValueError("B-07A leaves the prior capability explicitly unavailable")
    if (
        manifest.practice_scope_ref is not None
        or manifest.practice_pack_refs
        or manifest.scaffold_catalog_ref is not None
    ):
        raise ValueError(
            "B-07A cannot populate downstream practice/scaffold capability"
        )


class InMemoryDiscoveryProvider(ChallengeCatalogProvider, ManifestProvider):
    """Immutable exact-version discovery store for fixtures and local agents."""

    __slots__ = ("_infos", "_manifests")

    def __init__(self, resources: tuple[DiscoveryResourceVersion, ...]) -> None:
        if type(resources) is not tuple or len(resources) > 256:
            raise ValueError("discovery catalog must be a bounded exact tuple")
        if any(type(item) is not DiscoveryResourceVersion for item in resources):
            raise TypeError(
                "discovery catalog values must use their exact nominal type"
            )
        infos: dict[ChallengeKey, bytes] = {}
        manifests: dict[ChallengeKey, bytes] = {}
        for item in resources:
            key = item.challenge_info.challenge_key
            if key in infos:
                raise ValueError(
                    "discovery catalog contains a duplicate Challenge version"
                )
            infos[key] = canonical_bytes(item.challenge_info)
            manifests[key] = canonical_bytes(item.interaction_manifest)
        self._infos = infos
        self._manifests = manifests

    def get_challenge_info(self, challenge_key: ChallengeKey) -> ChallengeInfo:
        if type(challenge_key) is not ChallengeKey:
            raise KeyError
        try:
            payload = self._infos[challenge_key]
        except KeyError:
            raise KeyError from None
        return load_canonical(payload, ChallengeInfo)  # type: ignore[return-value]

    def get_interaction_manifest(
        self, challenge_key: ChallengeKey
    ) -> InteractionManifest:
        if type(challenge_key) is not ChallengeKey:
            raise KeyError
        try:
            payload = self._manifests[challenge_key]
        except KeyError:
            raise KeyError from None
        return load_canonical(payload, InteractionManifest)  # type: ignore[return-value]


_REQUEST_TYPES = {
    "get_challenge_info": GetChallengeInfoRequest,
    "get_interaction_manifest": GetInteractionManifestRequest,
}


def _failure(code: ResearchServiceErrorCode) -> ServiceReply:
    return ServiceReply(ReplyStatus.ERROR, public_error(code))


class LocalDiscoveryAdapter:
    """In-process discovery only; no listener, credential, task, or v1 authority."""

    __slots__ = ("_catalog", "_manifest")

    def __init__(
        self,
        challenge_catalog_provider: ChallengeCatalogProvider,
        manifest_provider: ManifestProvider,
    ) -> None:
        if challenge_catalog_provider is None or not callable(
            getattr(challenge_catalog_provider, "get_challenge_info", None)
        ):
            raise TypeError("a ChallengeCatalogProvider is required")
        if manifest_provider is None or not callable(
            getattr(manifest_provider, "get_interaction_manifest", None)
        ):
            raise TypeError("a ManifestProvider is required")
        self._catalog = challenge_catalog_provider
        self._manifest = manifest_provider

    def call(self, call: object) -> ServiceReply:
        if type(call) is not ServiceCall:
            return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if call.namespace != RESEARCH_NAMESPACE:
            return _failure(ResearchServiceErrorCode.NAMESPACE_MISMATCH)
        if call.operation in OFFICIAL_V1_OPERATIONS:
            return _failure(ResearchServiceErrorCode.NAMESPACE_MISMATCH)
        if call.operation not in SUPPORTED_OPERATIONS:
            return _failure(ResearchServiceErrorCode.OPERATION_UNSUPPORTED)
        expected = _REQUEST_TYPES.get(call.operation)
        if expected is None:
            return _failure(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)
        if type(call.request) is not expected:
            return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        challenge_key = call.request.challenge_key
        if type(challenge_key) is not ChallengeKey:
            return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)

        try:
            if call.operation == "get_challenge_info":
                result = self._catalog.get_challenge_info(challenge_key)
                if type(result) is not ChallengeInfo:
                    return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                if result.challenge_key != challenge_key:
                    return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
            else:
                result = self._manifest.get_interaction_manifest(challenge_key)
                if type(result) is not InteractionManifest:
                    return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                if result.challenge_key != challenge_key:
                    return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
                info = self._catalog.get_challenge_info(challenge_key)
                if type(info) is not ChallengeInfo:
                    return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                try:
                    _validate_pair(info, result)
                except (TypeError, ValueError):
                    return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
            # Reconstruct through the exact codec to reject mutated or hostile
            # provider carriers before any bytes leave the boundary.
            result = load_canonical(canonical_bytes(result), type(result))
            return ServiceReply(ReplyStatus.OK, result)
        except KeyError:
            return _failure(ResearchServiceErrorCode.CHALLENGE_NOT_FOUND)
        except DiscoveryProviderUnavailable:
            return _failure(ResearchServiceErrorCode.PROVIDER_UNAVAILABLE)
        except CanonicalWireError as exc:
            if exc.code is ResearchServiceErrorCode.BOUND_EXCEEDED:
                return _failure(exc.code)
            return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        except Exception:  # noqa: BLE001 - hostile providers cannot leak diagnostics
            return _failure(ResearchServiceErrorCode.INTERNAL_FAILURE)

    def call_bytes(self, payload: object) -> bytes:
        try:
            call = load_canonical(payload, ServiceCall)
        except CanonicalWireError as exc:
            return canonical_bytes(_failure(exc.code))
        return canonical_bytes(self.call(call))


__all__ = (
    "DiscoveryResourceVersion",
    "InMemoryDiscoveryProvider",
    "LocalDiscoveryAdapter",
)
