"""Provisioning lifecycle over a provider and the durable store."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from .accounting import committed_usd, request_bound_usd
from .errors import ComputeError, Execution
from .model import (
    CarbonOwnedResource,
    IntentState,
    Offer,
    ProvisionRequest,
    ResourceState,
    UserManagedHost,
    ownership_name,
)
from .provider import ComputeProvider
from .store import ComputeStore, IntentRecord, ResourceRecord

__all__ = ["ComputeService", "HealthResult"]

log = logging.getLogger("carbon.compute")


@dataclass(frozen=True)
class HealthResult:
    target: str
    healthy: bool
    http_status: int | None
    observed_at: float


class ComputeService:
    def __init__(
        self,
        store: ComputeStore,
        provider: ComputeProvider,
        *,
        clock: Callable[[], float] = time.time,
        not_found_grace_s: float = 600.0,
        max_balance_age_s: float | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.clock = clock
        self.not_found_grace_s = not_found_grace_s
        self.max_balance_age_s = max_balance_age_s

    # provisioning -------------------------------------------------------
    def provision(
        self, request: ProvisionRequest, *, offer: Offer | None = None
    ) -> ResourceRecord:
        """Idempotent per (campaign, intent id); never resends an ambiguous create.

        ``offer`` (an observed price) is kept as the estimate fallback when the
        provider's create response carries no rate.
        """

        if self.store.campaign_status(request.campaign_id) != "active":
            raise ComputeError(
                operation="provision",
                failed="campaign is not active",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="start the campaign before provisioning",
            )
        if request.deadline_at <= self.clock():
            raise ComputeError(
                operation="provision",
                failed="deadline already passed",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="set a future deadline",
            )
        intent, _created = self.store.begin_intent(request, provider=self.provider.name)
        if intent.state is IntentState.REQUESTED:
            self._spend_gate(request, offer)
        if intent.state is IntentState.BOUND:
            return self._primary(intent)
        if intent.state is IntentState.DISPATCHED:
            return self.recover(intent)
        if intent.state is not IntentState.REQUESTED:
            raise ComputeError(
                operation="provision",
                failed=f"intent is {intent.state}",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="use a new intent_id",
            )
        # Record "may have been sent" before sending.
        self.store.set_intent_state(
            intent.campaign_id,
            intent.intent_id,
            IntentState.DISPATCHED,
            offer_usd_per_hr=None if offer is None else offer.usd_per_hr,
        )
        log.info(
            "compute provision dispatched campaign=%s intent=%s",
            intent.campaign_id,
            intent.intent_id,
        )
        try:
            created = self.provider.create(
                request.spec, ownership_tag=intent.ownership_tag
            )
        except ComputeError as failure:
            if failure.execution is Execution.EXECUTED and not (
                failure.resources_may_remain
            ):
                self.store.set_intent_state(
                    intent.campaign_id, intent.intent_id, IntentState.REJECTED
                )
            raise
        record = self.store.bind_resource(
            intent,
            created.resource_id,
            rate_usd_per_hr=created.rate_usd_per_hr,
            discovered_via="create_response",
        )
        ceiling = request.spec.max_rate_usd_per_hr
        if ceiling is not None and (
            created.rate_usd_per_hr is None or created.rate_usd_per_hr > ceiling
        ):
            self.terminate(intent.campaign_id, intent.intent_id, record.resource_id)
            raise ComputeError(
                operation="provision",
                failed="provider rate unknown or above the request's ceiling; "
                "terminated",
                execution=Execution.EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="choose another offer and use a new intent_id",
            )
        return record

    def observe_balance(self, campaign_id: str) -> tuple[float, float]:
        """Read the account balance from the provider and record it for the campaign."""

        seen = self.provider.read_balance()
        self.store.record_balance(
            self.provider.name,
            campaign_id,
            balance_usd=seen.balance_usd,
            observed_at=seen.observed_at,
            source=seen.source,
        )
        return seen.balance_usd, seen.observed_at

    def _spend_gate(self, request: ProvisionRequest, offer: Offer | None) -> None:
        """Refuse before dispatch unless the request fits the balance and budget.

        The account balance is the spending cap and must have been observed and
        recorded for this campaign; the miner's own budget, when lower, applies
        on top. Commitments are conservative (live resources to their deadline).
        """

        def refuse(failed: str, next_action: str) -> ComputeError:
            return ComputeError(
                operation="provision",
                failed=failed,
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action=next_action,
            )

        now = self.clock()
        balance = self.store.latest_balance(self.provider.name, request.campaign_id)
        if balance is None:
            raise refuse(
                "no account balance observation recorded for this campaign",
                "observe and record the balance before the first provision",
            )
        balance_usd, observed_at = balance
        if (
            self.max_balance_age_s is not None
            and now - observed_at > self.max_balance_age_s
        ):
            raise refuse("balance observation is stale", "observe the balance again")
        spec = request.spec
        rate = spec.max_rate_usd_per_hr
        if rate is None and offer is not None:
            rate = offer.usd_per_hr
        bound = request_bound_usd(
            rate,
            spec.storage_gb,
            spec.storage_usd_per_gb_month,
            request.deadline_at - now,
        )
        if bound == float("inf"):
            raise refuse(
                "request cost is unbounded (no rate ceiling or storage rate)",
                "set max_rate_usd_per_hr and storage_usd_per_gb_month",
            )
        account = committed_usd(self.store, clock=self.clock)
        if account + bound > balance_usd:
            raise refuse(
                "request would exceed the observed account balance",
                "shorten the deadline, lower the rate, or add funds",
            )
        budget = self.store.miner_budget(request.campaign_id)
        if budget is not None:
            campaign = committed_usd(
                self.store, campaign_id=request.campaign_id, clock=self.clock
            )
            if campaign + bound > budget:
                raise refuse(
                    "request would exceed the miner's campaign budget",
                    "raise the budget or shorten the deadline",
                )

    def recover(self, intent: IntentRecord) -> ResourceRecord:
        """Resolve an ambiguous create by ownership tag. Adopts; never resends."""

        name = ownership_name(intent.ownership_tag)
        matches = sorted(
            item.resource_id
            for item in self.provider.list_resources()
            if item.name == name
        )
        for resource_id in matches:
            self.store.bind_resource(
                intent,
                resource_id,
                rate_usd_per_hr=None,
                discovered_via="tag_reconcile",
            )
        if matches:
            refreshed = self.store.intent(intent.campaign_id, intent.intent_id)
            assert refreshed is not None
            return self._primary(refreshed)
        expired = self.clock() - intent.created_at > self.not_found_grace_s
        if expired:
            self.store.set_intent_state(
                intent.campaign_id, intent.intent_id, IntentState.NOT_FOUND
            )
        raise ComputeError(
            operation="provision",
            failed="dispatched request not found by ownership tag",
            execution=Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=not expired,
            retry_safe=False,
            next_action=(
                "use a new intent_id; the reconciler still adopts and terminates "
                "any late resource with this tag"
                if expired
                else "wait and reconcile; do not resend"
            ),
        )

    def _primary(self, intent: IntentRecord) -> ResourceRecord:
        for record in self.store.resources(intent.campaign_id, intent.intent_id):
            if record.role == "primary":
                return record
        raise AssertionError("bound intent without a primary resource")

    # lifecycle ----------------------------------------------------------
    def refresh(self, campaign_id: str, intent_id: str) -> list[ResourceRecord]:
        for record in self.store.resources(campaign_id, intent_id):
            if record.state in {ResourceState.TERMINATED, ResourceState.EXPORTING}:
                continue
            seen = self.provider.observe(record.resource_id)
            self.store.set_resource_state(
                record.provider, record.resource_id, seen.state
            )
        return self.store.resources(campaign_id, intent_id)

    def mark_exporting(self, owned: CarbonOwnedResource) -> None:
        """Carbon-level state: results are being fetched from a running resource."""

        self.store.set_resource_state(
            owned.provider, owned.resource_id, ResourceState.EXPORTING
        )

    def owned(
        self, campaign_id: str, intent_id: str, resource_id: str
    ) -> CarbonOwnedResource:
        return self.store.owned(campaign_id, intent_id, resource_id)

    def stop(self, campaign_id: str, intent_id: str, resource_id: str) -> None:
        owned = self.store.owned(campaign_id, intent_id, resource_id)
        self.provider.stop(owned)
        self.store.set_resource_state(
            owned.provider, resource_id, ResourceState.STOPPED
        )

    def terminate(self, campaign_id: str, intent_id: str, resource_id: str) -> None:
        owned = self.store.owned(campaign_id, intent_id, resource_id)
        self.store.set_resource_state(
            owned.provider, resource_id, ResourceState.TERMINATING
        )
        self.provider.terminate(owned)
        self.store.set_resource_state(
            owned.provider, resource_id, ResourceState.TERMINATED
        )

    def cancel_provisioning(self, campaign_id: str, intent_id: str) -> IntentState:
        intent = self.store.intent(campaign_id, intent_id)
        if intent is None:
            raise ComputeError(
                operation="cancel",
                failed="unknown intent",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="check the campaign and intent ids",
            )
        if intent.state is IntentState.REQUESTED:
            self.store.set_intent_state(campaign_id, intent_id, IntentState.CANCELLED)
            return IntentState.CANCELLED
        if intent.state is IntentState.DISPATCHED:
            self.recover(intent)  # raises if still unresolved
        for record in self.store.resources(campaign_id, intent_id):
            if record.state is not ResourceState.TERMINATED:
                self.terminate(campaign_id, intent_id, record.resource_id)
        refreshed = self.store.intent(campaign_id, intent_id)
        assert refreshed is not None
        return refreshed.state

    def health_check(
        self,
        target: CarbonOwnedResource | UserManagedHost,
        probe: Callable[[str], int],
        *,
        port: int = 8000,
        path: str = "/status",
    ) -> HealthResult:
        if isinstance(target, UserManagedHost):
            base, label = target.address.rstrip("/"), target.host_id
        else:
            base, label = self.provider.connect_url(target, port), target.resource_id
        try:
            status: int | None = int(probe(base + path))
        except Exception as failure:  # noqa: BLE001 -- health is a typed answer
            log.info("health probe failed (%s)", type(failure).__name__)
            status = None
        return HealthResult(label, status == 200, status, self.clock())
