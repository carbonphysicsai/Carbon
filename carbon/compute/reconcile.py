"""Independent reconciler: runnable without the controller.

It lists the provider account once and then:

* adopts live resources carrying the ownership tag of a known intent (a lost
  create response resolves here);
* reports live resources carrying a well-formed Carbon tag that no intent in
  this store owns (``orphans``) without touching them - another store, or a
  record lost with its root, may own them;
* terminates Carbon-owned resources past policy: campaign stopped, deadline
  passed, or a duplicate created for an intent that already has a primary;
* marks recorded resources that are verifiably absent as terminated;
* never acts on, and never lists by id, an untagged resource.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from .errors import ComputeError
from .model import OWNERSHIP_NAME_PATTERN, IntentState, ResourceState
from .provider import ComputeProvider
from .service import ComputeService
from .store import ComputeStore

__all__ = ["ReconcileReport", "reconcile"]


@dataclass
class ReconcileReport:
    observed_at: float
    adopted: list[str] = field(default_factory=list)
    terminated: list[dict[str, str]] = field(default_factory=list)
    already_absent: list[str] = field(default_factory=list)
    orphans: list[dict[str, str]] = field(default_factory=list)
    unresolved_dispatches: list[dict[str, str]] = field(default_factory=list)
    failures: list[dict[str, object]] = field(default_factory=list)
    untagged_ignored: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _policy_reason(store: ComputeStore, record, intent, now: float) -> str | None:
    if record.state is ResourceState.TERMINATING:
        return "termination_incomplete"
    if record.role == "duplicate":
        return "duplicate_for_intent"
    if store.campaign_status(record.campaign_id) != "active":
        return "campaign_stopped"
    if now >= intent.deadline_at:
        return "deadline_passed"
    return None


def reconcile(
    store: ComputeStore,
    provider: ComputeProvider,
    *,
    clock: Callable[[], float] = time.time,
) -> ReconcileReport:
    now = clock()
    report = ReconcileReport(observed_at=now)
    service = ComputeService(store, provider, clock=clock)
    live = provider.list_resources()
    live_ids = {item.resource_id for item in live}

    for item in live:
        match = OWNERSHIP_NAME_PATTERN.fullmatch(item.name or "")
        if match is None:
            report.untagged_ignored += 1
            continue
        intent = store.intent_by_tag(match.group(1))
        if intent is None or intent.provider != provider.name:
            report.orphans.append({"resource_id": item.resource_id, "name": item.name})
            continue
        if store.resource(provider.name, item.resource_id) is None:
            store.bind_resource(
                intent,
                item.resource_id,
                rate_usd_per_hr=None,
                discovered_via="tag_reconcile",
            )
            report.adopted.append(item.resource_id)

    for intent in store.intents(IntentState.DISPATCHED):
        report.unresolved_dispatches.append(
            {"campaign_id": intent.campaign_id, "intent_id": intent.intent_id}
        )

    for record in store.resources():
        if record.provider != provider.name or record.state is ResourceState.TERMINATED:
            continue
        intent = store.intent(record.campaign_id, record.intent_id)
        assert intent is not None
        try:
            if (
                record.resource_id not in live_ids
                and not provider.observe(record.resource_id).present
            ):
                store.set_resource_state(
                    record.provider, record.resource_id, ResourceState.TERMINATED
                )
                report.already_absent.append(record.resource_id)
                continue
            reason = _policy_reason(store, record, intent, now)
            if reason is None:
                continue
            service.terminate(record.campaign_id, record.intent_id, record.resource_id)
            report.terminated.append(
                {"resource_id": record.resource_id, "reason": reason}
            )
        except ComputeError as failure:
            report.failures.append(
                {"resource_id": record.resource_id, **failure.as_dict()}
            )
    return report
