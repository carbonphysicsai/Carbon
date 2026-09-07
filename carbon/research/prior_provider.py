"""B-07D3 authorized static PriorPack retrieval and structural alignment."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Protocol

from carbon.construction.catalog import ParameterCatalog, catalog_entries_by_surface

from .canonical import _canonical_tuple_payload
from .errors import ResearchServiceErrorCode
from .model import (
    ActivePriorSelector,
    AlignmentIssue,
    ExactPriorSelector,
    FixturePriorAuthorization,
    GetPriorRequest,
    InspectPriorAlignmentRequest,
    PriorAlignmentResult,
    PriorAlignmentStatus,
    PriorLookupResult,
    PriorLookupStatus,
    PriorPublicationClass,
    PublicPriorAuthorization,
)
from .prior_store import PriorLifecycle, PriorPackStore, PriorStoreError
from .records import PriorResolution
from .refs import PriorAlignmentRef, PriorChannel, PriorPackRef


def _lookup_exact(store: PriorPackStore, ref: PriorPackRef) -> PriorLookupResult:
    pack = store.read_pack(ref)
    snapshot_ref, authorization = store.authorization_for(ref)
    lifecycle = store.lifecycle(ref)
    if lifecycle is PriorLifecycle.WITHDRAWN:
        raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
    status = (
        PriorLookupStatus.ACTIVE
        if lifecycle is PriorLifecycle.ACTIVE
        else PriorLookupStatus.SUPERSEDED
    )
    return PriorLookupResult(snapshot_ref, pack, ref, status, authorization)


class StaticPublicPriorProvider:
    """Read already-authorized PUBLIC packs; it has no publication capability."""

    __slots__ = ("_store",)

    def __init__(self, store: PriorPackStore) -> None:
        if type(store) is not PriorPackStore:
            raise TypeError("public provider requires the exact static store")
        self._store = store

    def get_prior(self, request: GetPriorRequest) -> PriorLookupResult:
        if type(request) is not GetPriorRequest:
            raise PriorStoreError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        selector = request.selector
        if type(selector) is ExactPriorSelector:
            ref = selector.prior_pack_ref
            if ref.channel is not PriorChannel.PUBLIC:
                raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
            result = _lookup_exact(self._store, ref)
        elif type(selector) is ActivePriorSelector:
            if selector.channel is not PriorChannel.PUBLIC:
                raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
            result = self._active_with_one_retry(request)
        else:
            raise PriorStoreError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if (
            result.prior_pack.challenge_key != request.challenge_key
            or result.prior_pack.publication_class is PriorPublicationClass.TEST_ONLY
            or type(result.authorization) is not PublicPriorAuthorization
        ):
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        return result

    def _active_with_one_retry(self, request: GetPriorRequest) -> PriorLookupResult:
        for attempt in range(2):
            first = self._store.current_snapshot_ref(
                request.challenge_key, PriorChannel.PUBLIC
            )
            if first is None:
                raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
            snapshot = self._store.read_snapshot(first)
            active = snapshot.active_prior_pack_ref
            second = self._store.current_snapshot_ref(
                request.challenge_key, PriorChannel.PUBLIC
            )
            if first == second and active is not None:
                return _lookup_exact(self._store, active)
            if attempt:
                break
        raise PriorStoreError(ResearchServiceErrorCode.PRIOR_INDEX_CHANGED)


class _FixtureCapability:
    __slots__ = ()


_FIXTURE_CAPABILITY = _FixtureCapability()


class StaticTestOnlyPriorProvider:
    """Private exact-ref-only provider with a nominal fixture capability."""

    __slots__ = ("_now_micros", "_store")

    def __init__(
        self,
        store: PriorPackStore,
        capability: _FixtureCapability,
        *,
        now_micros: Callable[[], int],
    ) -> None:
        if type(store) is not PriorPackStore or capability is not _FIXTURE_CAPABILITY:
            raise TypeError("fixture provider requires its nominal private capability")
        self._store = store
        self._now_micros = now_micros

    @classmethod
    def for_test_fixture(
        cls, store: PriorPackStore, *, now_micros: Callable[[], int]
    ) -> StaticTestOnlyPriorProvider:
        return cls(store, _FIXTURE_CAPABILITY, now_micros=now_micros)

    def get_prior(self, request: GetPriorRequest) -> PriorLookupResult:
        if (
            type(request) is not GetPriorRequest
            or type(request.selector) is not ExactPriorSelector
        ):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        ref = request.selector.prior_pack_ref
        if (
            ref.channel is not PriorChannel.TEST_ONLY_FIXTURE
            or ref.challenge_key != request.challenge_key
        ):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        result = _lookup_exact(self._store, ref)
        if (
            result.prior_pack.publication_class is not PriorPublicationClass.TEST_ONLY
            or type(result.authorization) is not FixturePriorAuthorization
        ):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        receipt = self._store.fixture_authorization(result.authorization.receipt_ref)
        if (
            receipt.prior_pack_ref != ref
            or self._now_micros() >= receipt.expires_at_micros
        ):
            raise PriorStoreError(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        return result


class _PriorReader(Protocol):
    def get_prior(self, request: GetPriorRequest) -> PriorLookupResult: ...


class StaticPriorResolver:
    """B-07B adapter: resolve once so task records pin snapshot and pack refs."""

    def __init__(self, provider: _PriorReader) -> None:
        self._provider = provider

    def resolve_prior(self, request: GetPriorRequest) -> PriorResolution:
        result = self._provider.get_prior(request)
        return PriorResolution(result.index_snapshot_ref, result.prior_pack_ref)


def _walk_public_strategy(value: object, *, depth: int = 0) -> tuple[str, ...]:
    if depth > 32:
        raise PriorStoreError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    if type(value) is dict:
        output: list[str] = []
        for key in sorted(value):
            if type(key) is not str:
                raise PriorStoreError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
            output.append(key)
            output.extend(_walk_public_strategy(value[key], depth=depth + 1))
        return tuple(output)
    if type(value) is list:
        return tuple(
            token
            for item in value
            for token in _walk_public_strategy(item, depth=depth + 1)
        )
    return ()


class DeterministicPriorAlignmentProvider:
    """Structural-only alignment from a pinned pack and public catalog."""

    __slots__ = ("_catalog", "_provider")

    def __init__(
        self, provider: _PriorReader, parameter_catalog: ParameterCatalog
    ) -> None:
        if type(parameter_catalog) is not ParameterCatalog:
            raise TypeError("alignment requires the exact public ParameterCatalog")
        self._provider = provider
        self._catalog = parameter_catalog

    def inspect_prior_alignment(
        self, request: InspectPriorAlignmentRequest
    ) -> PriorAlignmentResult:
        if type(request) is not InspectPriorAlignmentRequest:
            raise PriorStoreError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if request.challenge_key != self._catalog.challenge_key:
            raise PriorStoreError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        lookup = self._provider.get_prior(
            GetPriorRequest(
                request.challenge_key, ExactPriorSelector(request.prior_pack_ref)
            )
        )
        catalog_surfaces = set(catalog_entries_by_surface(self._catalog))
        strategy_surfaces = (
            set(_walk_public_strategy(request.strategy)) & catalog_surfaces
        )
        relevant = {item.intervention.surface_id for item in lookup.prior_pack.items}
        matched = sorted(relevant & strategy_surfaces)
        missing = sorted(relevant - strategy_surfaces)
        if not relevant:
            status = PriorAlignmentStatus.NOT_APPLICABLE
        elif matched and not missing:
            status = PriorAlignmentStatus.ALIGNED
        elif matched:
            status = PriorAlignmentStatus.PARTIAL
        else:
            status = PriorAlignmentStatus.NOT_ALIGNED
        issues = tuple(
            AlignmentIssue(
                "prior_surface_not_selected",
                ("strategy", surface_id),
                "A prior-covered public catalog surface is not selected.",
            )
            for surface_id in missing
        )
        digest = (
            "sha256:"
            + hashlib.sha256(
                b"carbon.prior-alignment.v2\x00"
                + _canonical_tuple_payload(
                    (request, lookup.prior_pack_ref, status, issues)
                )
            ).hexdigest()
        )
        return PriorAlignmentResult(
            PriorAlignmentRef(request.challenge_key, content_digest=digest),
            status,
            issues,
        )


__all__ = (
    "DeterministicPriorAlignmentProvider",
    "StaticPriorResolver",
    "StaticPublicPriorProvider",
    "StaticTestOnlyPriorProvider",
)
