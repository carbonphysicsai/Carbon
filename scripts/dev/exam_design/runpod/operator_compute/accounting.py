"""Compute accounting: estimates, provider-reported charges and unresolved.

The three are never summed together. An estimate is Carbon arithmetic over
recorded state intervals and caller/provider-observed rates; a provider charge
is what the provider reported; a resource with no provider report is listed as
unresolved rather than filled in from its estimate. Storage is estimated for
every interval it persists, including while a resource is stopped.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from .model import COMPUTE_BILLED, STORAGE_BILLED, ResourceState
from .provider import ComputeProvider
from .store import ComputeStore

__all__ = [
    "AccountingSummary",
    "ResourceAccount",
    "collect_charges",
    "committed_usd",
    "request_bound_usd",
    "summarize",
]

HOURS_PER_MONTH = 730.0


@dataclass(frozen=True)
class ResourceAccount:
    resource_id: str
    campaign_id: str
    state: str
    compute_hours: float
    storage_gb_hours: float
    estimated_compute_usd: float | None
    estimated_storage_usd: float | None
    provider_reported_usd: float | None


@dataclass(frozen=True)
class AccountingSummary:
    resources: tuple[ResourceAccount, ...]
    estimated_usd: float
    estimate_unresolved: tuple[str, ...]
    provider_reported_usd: float
    provider_unresolved: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _intervals(
    events: list[tuple[str, float]], now: float
) -> list[tuple[ResourceState, float]]:
    out = []
    for index, (state, start) in enumerate(events):
        end = events[index + 1][1] if index + 1 < len(events) else now
        out.append((ResourceState(state), max(0.0, end - start)))
    return out


def summarize(
    store: ComputeStore,
    *,
    campaign_id: str | None = None,
    clock: Callable[[], float] = time.time,
) -> AccountingSummary:
    now = clock()
    accounts = []
    for record in store.resources(campaign_id):
        intent = store.intent(record.campaign_id, record.intent_id)
        assert intent is not None
        spans = _intervals(store.state_events(record.provider, record.resource_id), now)
        compute_s = sum(s for state, s in spans if state in COMPUTE_BILLED)
        storage_s = sum(s for state, s in spans if state in STORAGE_BILLED)
        rate = (
            record.rate_usd_per_hr
            if record.rate_usd_per_hr is not None
            else intent.rate_bound_usd_per_hr
        )
        storage_gb_hours = intent.storage_gb * storage_s / 3600
        compute_usd = None if rate is None else rate * compute_s / 3600
        storage_usd = (
            None
            if intent.storage_usd_per_gb_month is None
            else storage_gb_hours * intent.storage_usd_per_gb_month / HOURS_PER_MONTH
        )
        if intent.storage_gb == 0:
            storage_usd = 0.0
        charges = store.provider_charges(record.provider, record.resource_id)
        accounts.append(
            ResourceAccount(
                record.resource_id,
                record.campaign_id,
                str(record.state),
                compute_s / 3600,
                storage_gb_hours,
                compute_usd,
                storage_usd,
                sum(charges) if charges else None,
            )
        )
    return AccountingSummary(
        resources=tuple(accounts),
        estimated_usd=sum(
            (a.estimated_compute_usd or 0.0) + (a.estimated_storage_usd or 0.0)
            for a in accounts
        ),
        estimate_unresolved=tuple(
            a.resource_id
            for a in accounts
            if a.estimated_compute_usd is None or a.estimated_storage_usd is None
        ),
        provider_reported_usd=sum(a.provider_reported_usd or 0.0 for a in accounts),
        provider_unresolved=tuple(
            a.resource_id for a in accounts if a.provider_reported_usd is None
        ),
    )


def collect_charges(store: ComputeStore, provider: ComputeProvider) -> list[str]:
    """Record provider-reported charges; returns resource ids still unresolved."""

    unresolved = []
    for record in store.resources():
        if record.provider != provider.name:
            continue
        owned = store.owned(record.campaign_id, record.intent_id, record.resource_id)
        charge = provider.provider_charge(owned)
        if charge is None:
            unresolved.append(record.resource_id)
            continue
        store.record_provider_charge(
            record.provider, record.resource_id, charge.amount_usd, charge.basis
        )
    return unresolved


def request_bound_usd(
    rate_usd_per_hr: float | None,
    storage_gb: float,
    storage_usd_per_gb_month: float | None,
    seconds: float,
) -> float:
    """Worst-case cost of holding a resource for ``seconds``; ``inf`` if unbounded."""

    if rate_usd_per_hr is None or (storage_gb and storage_usd_per_gb_month is None):
        return float("inf")
    storage_hourly = storage_gb * (storage_usd_per_gb_month or 0.0) / HOURS_PER_MONTH
    return max(0.0, seconds) / 3600 * (rate_usd_per_hr + storage_hourly)


def committed_usd(
    store: ComputeStore,
    *,
    campaign_id: str | None = None,
    clock: Callable[[], float] = time.time,
) -> float:
    """Conservative committed spend: live resources count to their deadline.

    A dispatched intent whose resource is not yet known counts its full bound;
    an unbounded rate makes the commitment infinite, so a gate refuses.
    """

    from .model import IntentState

    now = clock()
    total = 0.0
    for intent in store.intents(IntentState.DISPATCHED, IntentState.BOUND):
        if campaign_id is not None and intent.campaign_id != campaign_id:
            continue
        records = store.resources(intent.campaign_id, intent.intent_id)
        if not records:
            total += request_bound_usd(
                intent.rate_bound_usd_per_hr,
                intent.storage_gb,
                intent.storage_usd_per_gb_month,
                max(intent.deadline_at, now) - intent.created_at,
            )
            continue
        for record in records:
            rate = (
                record.rate_usd_per_hr
                if record.rate_usd_per_hr is not None
                else intent.rate_bound_usd_per_hr
            )
            spans = _intervals(
                store.state_events(record.provider, record.resource_id), now
            )
            compute_s = sum(s for state, s in spans if state in COMPUTE_BILLED)
            storage_s = sum(s for state, s in spans if state in STORAGE_BILLED)
            spent = request_bound_usd(rate, 0, None, compute_s) + request_bound_usd(
                0.0, intent.storage_gb, intent.storage_usd_per_gb_month, storage_s
            )
            remaining = 0.0
            if record.state is not ResourceState.TERMINATED:
                remaining = request_bound_usd(
                    rate,
                    intent.storage_gb,
                    intent.storage_usd_per_gb_month,
                    intent.deadline_at - now,
                )
            total += spent + remaining
    return total
