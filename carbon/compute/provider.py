"""The provider-neutral compute interface."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .model import CarbonOwnedResource, Offer, PodSpec, ResourceState

__all__ = [
    "BalanceObservation",
    "ComputeProvider",
    "CreateResult",
    "ListedResource",
    "Observation",
    "ProviderCharge",
]


@dataclass(frozen=True)
class CreateResult:
    resource_id: str
    rate_usd_per_hr: float | None


@dataclass(frozen=True)
class Observation:
    resource_id: str
    present: bool
    state: ResourceState
    name: str | None
    rate_usd_per_hr: float | None
    observed_at: float


@dataclass(frozen=True)
class ListedResource:
    resource_id: str
    name: str | None


@dataclass(frozen=True)
class BalanceObservation:
    """An account balance, with when and where it was observed."""

    balance_usd: float
    observed_at: float
    source: str


@dataclass(frozen=True)
class ProviderCharge:
    """A provider-reported charge. Never derived from a Carbon estimate."""

    amount_usd: float
    basis: str


class ComputeProvider(Protocol):
    name: str

    def offers(
        self, gpu_type_ids: Sequence[str], *, gpu_count: int, cloud_type: str
    ) -> list[Offer]: ...

    def read_balance(self) -> BalanceObservation: ...

    def create(self, spec: PodSpec, *, ownership_tag: str) -> CreateResult: ...

    def observe(self, resource_id: str) -> Observation: ...

    def list_resources(self) -> list[ListedResource]: ...

    def stop(self, owned: CarbonOwnedResource) -> None: ...

    def terminate(self, owned: CarbonOwnedResource) -> bool: ...

    def connect_url(self, owned: CarbonOwnedResource, port: int) -> str: ...

    def provider_charge(self, owned: CarbonOwnedResource) -> ProviderCharge | None: ...
