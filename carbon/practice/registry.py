"""Versioned mock-pack and non-champion scaffold registries for B-07C."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from carbon.authoring.primitives import validate_version_token
from carbon.authoring.refs import TrainingSupportContractRef
from carbon.registry import ChallengeKey
from carbon.research import (
    GetMockScaffoldRequest,
    MockScaffold,
    MockScaffoldRef,
    PriorPackRef,
    canonical_bytes,
    load_canonical,
)

from .model import MockPracticePack, PracticeScopeStatement


class MockPackRegistryError(LookupError):
    pass


class VersionedMockPackRegistry:
    """Immutable exact-ref lookup; no latest alias or official-pack fallback."""

    __slots__ = ("_by_challenge", "_by_scope", "_packs", "_scopes")

    def __init__(
        self,
        *,
        scopes: tuple[PracticeScopeStatement, ...],
        packs: tuple[MockPracticePack, ...],
    ) -> None:
        if type(scopes) is not tuple or type(packs) is not tuple or not packs:
            raise TypeError("mock registry inputs must be exact nonempty tuples")
        if any(type(item) is not PracticeScopeStatement for item in scopes) or any(
            type(item) is not MockPracticePack for item in packs
        ):
            raise TypeError("mock registry rejects substituted record types")
        scope_map = {item.to_ref(): item for item in scopes}
        if len(scope_map) != len(scopes):
            raise ValueError("practice scope identities must be unique")
        pack_map = {item.to_ref(): item for item in packs}
        if len(pack_map) != len(packs):
            raise ValueError("mock pack identities must be unique")
        by_scope: dict[object, list[MockPracticePack]] = {}
        by_challenge: dict[ChallengeKey, list[MockPracticePack]] = {}
        for pack in packs:
            scope = scope_map.get(pack.practice_scope_ref)
            if scope is None or scope.challenge_key != pack.challenge_key:
                raise ValueError("mock pack has no exact registered practice scope")
            by_scope.setdefault(pack.practice_scope_ref, []).append(pack)
            by_challenge.setdefault(pack.challenge_key, []).append(pack)
        self._packs = pack_map
        self._scopes = scope_map
        self._by_scope = {key: tuple(value) for key, value in by_scope.items()}
        self._by_challenge = {key: tuple(value) for key, value in by_challenge.items()}

    def get(self, pack_ref):
        try:
            return self._packs[pack_ref]
        except (KeyError, TypeError):
            raise MockPackRegistryError("mock pack reference is unavailable") from None

    def resolve_scope(self, scope_ref):
        try:
            packs = self._by_scope[scope_ref]
        except (KeyError, TypeError):
            raise MockPackRegistryError("practice scope is unavailable") from None
        if len(packs) != 1:
            raise MockPackRegistryError("practice scope is not uniquely versioned")
        return packs[0]

    def resolve_calibration(self, challenge_key: ChallengeKey) -> MockPracticePack:
        if type(challenge_key) is not ChallengeKey:
            raise MockPackRegistryError("calibration Challenge is invalid")
        packs = self._by_challenge.get(challenge_key, ())
        if len(packs) != 1:
            raise MockPackRegistryError("calibration pack is not uniquely versioned")
        return packs[0]


@dataclass(frozen=True, slots=True)
class RegisteredMockScaffold:
    challenge_key: ChallengeKey
    version: str
    training_support_ref: TrainingSupportContractRef
    prior_pack_ref: PriorPackRef | None
    strategy_template: dict[str, object]
    limitations: tuple[str, ...] = ("MOCK_ONLY", "NON_CHAMPION")

    def __post_init__(self) -> None:
        if type(self) is not RegisteredMockScaffold:
            raise TypeError("scaffold registration subclasses are rejected")
        if type(self.challenge_key) is not ChallengeKey:
            raise TypeError("scaffold requires an exact ChallengeKey")
        validate_version_token(self.version, "version")
        if (
            type(self.training_support_ref) is not TrainingSupportContractRef
            or self.training_support_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("scaffold training support has a Challenge mismatch")
        if self.prior_pack_ref is not None and (
            type(self.prior_pack_ref) is not PriorPackRef
            or self.prior_pack_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("scaffold prior has a Challenge mismatch")
        if type(self.strategy_template) is not dict:
            raise TypeError("scaffold strategy must use the shared Strategy shape")
        if (
            type(self.limitations) is not tuple
            or "MOCK_ONLY" not in self.limitations
            or "NON_CHAMPION" not in self.limitations
        ):
            raise ValueError("scaffold must declare MOCK_ONLY and NON_CHAMPION")

    def resource(self) -> MockScaffold:
        digest = (
            "sha256:"
            + hashlib.sha256(
                b"carbon.mock-scaffold.v1\x00"
                + canonical_bytes(
                    MockScaffold(
                        MockScaffoldRef(
                            self.challenge_key, content_digest="sha256:" + "0" * 64
                        ),
                        self.strategy_template,
                        self.limitations,
                    )
                )
            ).hexdigest()
        )
        return MockScaffold(
            MockScaffoldRef(self.challenge_key, content_digest=digest),
            self.strategy_template,
            self.limitations,
        )


class InMemoryScaffoldProvider:
    __slots__ = ("_resources",)

    def __init__(self, registrations: tuple[RegisteredMockScaffold, ...]) -> None:
        if (
            type(registrations) is not tuple
            or not registrations
            or any(type(item) is not RegisteredMockScaffold for item in registrations)
        ):
            raise TypeError("scaffold registrations must be an exact nonempty tuple")
        resources: dict[
            tuple[ChallengeKey, TrainingSupportContractRef, PriorPackRef | None], bytes
        ] = {}
        for item in registrations:
            key = (item.challenge_key, item.training_support_ref, item.prior_pack_ref)
            if key in resources:
                raise ValueError("scaffold registration key is duplicated")
            resources[key] = canonical_bytes(item.resource())
        self._resources = resources

    def get_mock_scaffold(self, request: GetMockScaffoldRequest) -> MockScaffold:
        if type(request) is not GetMockScaffoldRequest:
            raise TypeError("get_mock_scaffold requires the exact shared request")
        key = (
            request.challenge_key,
            request.training_support_ref,
            request.prior_pack_ref,
        )
        try:
            payload = self._resources[key]
        except KeyError:
            raise KeyError("mock scaffold is unavailable") from None
        result = load_canonical(payload, MockScaffold)
        assert type(result) is MockScaffold
        return result


__all__ = (
    "InMemoryScaffoldProvider",
    "MockPackRegistryError",
    "RegisteredMockScaffold",
    "VersionedMockPackRegistry",
)
