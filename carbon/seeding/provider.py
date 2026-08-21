"""Fail-closed provider boundaries for A4 seeding contexts."""

from __future__ import annotations

from typing import Protocol

from carbon.seeding.model import (
    FixtureOfficialContext,
    FixtureOfficialEntropy,
    OfficialContext,
    OfficialEntropy,
    SeedPin,
    SeedValidationError,
)


class BeaconProvider(Protocol):
    """Narrow boundary for one opaque provider-origin observation."""

    def observe_entropy(self) -> OfficialEntropy:
        """Return one exact provider-origin entropy observation."""
        ...


class BeaconConflictError(RuntimeError):
    """Signal that a provider observed conflicting official material."""


class OfficialEntropyUnavailable(RuntimeError):
    """Stable public failure for any unusable official observation."""


class FixtureEntropyUnavailable(RuntimeError):
    """Stable public failure for any unusable fixture observation."""


_OBSERVATION_FAILED = object()


def _observe_official_once(provider: BeaconProvider) -> object:
    try:
        observation = provider.observe_entropy()
        if type(observation) is not OfficialEntropy:
            return _OBSERVATION_FAILED
        return OfficialEntropy(observation._copy_bytes())
    except Exception:  # noqa: BLE001 - the provider boundary must fail closed.
        return _OBSERVATION_FAILED


def acquire_official_context(provider: BeaconProvider, pin: SeedPin) -> OfficialContext:
    """Acquire one immutable official context or fail without a fallback."""
    if type(pin) is not SeedPin:
        del provider, pin
        raise SeedValidationError("official context requires an exact SeedPin")

    observation = _observe_official_once(provider)
    del provider
    if observation is _OBSERVATION_FAILED:
        observation = None
        del pin
        raise OfficialEntropyUnavailable("official entropy is unavailable") from None
    return OfficialContext._from_observation(observation, pin)


class DeterministicFixtureProvider:
    """Immutable deterministic provider for fixture-official tests only."""

    __slots__ = ("__entropy",)

    def __init__(self, entropy: FixtureOfficialEntropy) -> None:
        try:
            object.__getattribute__(
                self,
                "_DeterministicFixtureProvider__entropy",
            )
        except AttributeError:
            pass
        else:
            del entropy
            raise AttributeError("DeterministicFixtureProvider is immutable")
        if type(entropy) is not FixtureOfficialEntropy:
            del entropy
            raise SeedValidationError(
                "fixture provider requires exact FixtureOfficialEntropy"
            )
        object.__setattr__(
            self,
            "_DeterministicFixtureProvider__entropy",
            FixtureOfficialEntropy(entropy._copy_bytes()),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("DeterministicFixtureProvider is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("DeterministicFixtureProvider is immutable")

    def __repr__(self) -> str:
        return "DeterministicFixtureProvider(<redacted>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(
            "DeterministicFixtureProvider does not support generic serialization"
        )

    def __getstate__(self) -> object:
        raise TypeError(
            "DeterministicFixtureProvider does not support generic serialization"
        )

    def fixture_entropy(self) -> FixtureOfficialEntropy:
        """Return a fresh fixture-only wrapper around the fixed bytes."""
        return FixtureOfficialEntropy(self.__entropy._copy_bytes())


def _observe_fixture_once(provider: DeterministicFixtureProvider) -> object:
    try:
        observation = provider.fixture_entropy()
        if type(observation) is not FixtureOfficialEntropy:
            return _OBSERVATION_FAILED
        return FixtureOfficialEntropy(observation._copy_bytes())
    except Exception:  # noqa: BLE001 - the fixture boundary must fail closed.
        return _OBSERVATION_FAILED


def acquire_fixture_official_context(
    provider: DeterministicFixtureProvider,
    pin: SeedPin,
) -> FixtureOfficialContext:
    """Acquire one fixture-official context through the fixture-only API."""
    if type(pin) is not SeedPin:
        del provider, pin
        raise SeedValidationError("fixture context requires an exact SeedPin")
    if type(provider) is not DeterministicFixtureProvider:
        del provider, pin
        raise FixtureEntropyUnavailable("fixture entropy is unavailable") from None

    observation = _observe_fixture_once(provider)
    del provider
    if observation is _OBSERVATION_FAILED:
        observation = None
        del pin
        raise FixtureEntropyUnavailable("fixture entropy is unavailable") from None
    return FixtureOfficialContext._from_fixture(observation, pin)


__all__ = (
    "BeaconConflictError",
    "BeaconProvider",
    "DeterministicFixtureProvider",
    "FixtureEntropyUnavailable",
    "OfficialEntropyUnavailable",
    "acquire_fixture_official_context",
    "acquire_official_context",
)
