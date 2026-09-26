"""Durable compute state (sqlite under a caller-given root).

Ordering guarantees the service relies on:

* an intent (tenant, miner, campaign, request digest, ownership tag) is
  committed before any provider request is sent;
* the intent moves to ``DISPATCHED`` - "the provider may have received this" -
  before the request is sent, so a crash between send and response leaves a
  record that forbids a blind resend;
* a provider resource id is committed the moment it is known.
"""

from __future__ import annotations

import math
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .errors import ComputeError, Execution
from .model import (
    _STORE_ISSUED,
    CarbonOwnedResource,
    IntentState,
    ProvisionRequest,
    ResourceState,
    new_ownership_tag,
)

__all__ = ["ComputeStore", "IntentRecord", "ResourceRecord"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('active', 'stopped')),
    miner_budget_usd REAL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS balance_observations (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    balance_usd REAL NOT NULL,
    observed_at REAL NOT NULL,
    source TEXT NOT NULL,
    recorded_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS intents (
    campaign_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    miner TEXT NOT NULL,
    provider TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    ownership_tag TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    created_at REAL NOT NULL,
    deadline_at REAL NOT NULL,
    storage_gb REAL NOT NULL,
    storage_usd_per_gb_month REAL,
    max_rate_usd_per_hr REAL,
    offer_usd_per_hr REAL,
    PRIMARY KEY (campaign_id, intent_id)
);
CREATE TABLE IF NOT EXISTS resources (
    provider TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('primary', 'duplicate')),
    state TEXT NOT NULL,
    rate_usd_per_hr REAL,
    discovered_via TEXT NOT NULL,
    recorded_at REAL NOT NULL,
    PRIMARY KEY (provider, resource_id),
    FOREIGN KEY (campaign_id, intent_id) REFERENCES intents (campaign_id, intent_id)
);
CREATE TABLE IF NOT EXISTS state_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    state TEXT NOT NULL,
    at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_charges (
    provider TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    basis TEXT NOT NULL,
    observed_at REAL NOT NULL,
    PRIMARY KEY (provider, resource_id, basis)
);
"""


@dataclass(frozen=True)
class IntentRecord:
    campaign_id: str
    intent_id: str
    tenant: str
    miner: str
    provider: str
    request_digest: str
    ownership_tag: str
    state: IntentState
    created_at: float
    deadline_at: float
    storage_gb: float
    storage_usd_per_gb_month: float | None
    max_rate_usd_per_hr: float | None
    offer_usd_per_hr: float | None

    @property
    def rate_bound_usd_per_hr(self) -> float | None:
        """The highest hourly compute rate this intent may incur, if bounded."""

        return (
            self.max_rate_usd_per_hr
            if self.max_rate_usd_per_hr is not None
            else self.offer_usd_per_hr
        )


@dataclass(frozen=True)
class ResourceRecord:
    provider: str
    resource_id: str
    campaign_id: str
    intent_id: str
    role: str
    state: ResourceState
    rate_usd_per_hr: float | None
    discovered_via: str
    recorded_at: float


class ComputeStore:
    def __init__(self, root: Path, *, clock: Callable[[], float] = time.time):
        root = Path(root)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError("compute root must not be a symlink")
        self.path = root / "compute.sqlite3"
        self.clock = clock
        self._db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(SCHEMA)
        os.chmod(self.path, 0o600)

    def close(self) -> None:
        self._db.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield self._db
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")

    # campaigns ----------------------------------------------------------
    def start_campaign(
        self, campaign_id: str, *, miner_budget_usd: float | None = None
    ) -> None:
        """Mark a campaign active; the miner's optional budget applies below the balance."""

        if miner_budget_usd is not None and miner_budget_usd < 0:
            raise ValueError("miner budget must be non-negative")
        with self._tx() as db:
            db.execute(
                "INSERT INTO campaigns VALUES (?, 'active', ?, ?) ON CONFLICT "
                "(campaign_id) DO UPDATE SET status = 'active', "
                "miner_budget_usd = excluded.miner_budget_usd, "
                "updated_at = excluded.updated_at",
                (campaign_id, miner_budget_usd, self.clock()),
            )

    def stop_campaign(self, campaign_id: str) -> None:
        with self._tx() as db:
            db.execute(
                "UPDATE campaigns SET status = 'stopped', updated_at = ? "
                "WHERE campaign_id = ?",
                (self.clock(), campaign_id),
            )

    def miner_budget(self, campaign_id: str) -> float | None:
        row = self._db.execute(
            "SELECT miner_budget_usd FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        return None if row is None else row["miner_budget_usd"]

    def record_balance(
        self,
        provider: str,
        campaign_id: str,
        *,
        balance_usd: float,
        observed_at: float,
        source: str,
    ) -> None:
        if not math.isfinite(balance_usd) or observed_at > self.clock():
            raise ValueError(
                "balance observation must be a number observed in the past"
            )
        with self._tx() as db:
            db.execute(
                "INSERT INTO balance_observations (provider, campaign_id, "
                "balance_usd, observed_at, source, recorded_at) VALUES (?,?,?,?,?,?)",
                (provider, campaign_id, balance_usd, observed_at, source, self.clock()),
            )

    def latest_balance(
        self, provider: str, campaign_id: str
    ) -> tuple[float, float] | None:
        """``(balance_usd, observed_at)`` of the newest observation, if any."""

        row = self._db.execute(
            "SELECT balance_usd, observed_at FROM balance_observations "
            "WHERE provider = ? AND campaign_id = ? ORDER BY observed_at DESC, seq DESC",
            (provider, campaign_id),
        ).fetchone()
        return None if row is None else (row["balance_usd"], row["observed_at"])

    def campaign_status(self, campaign_id: str) -> str | None:
        row = self._db.execute(
            "SELECT status FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        return None if row is None else row["status"]

    # intents ------------------------------------------------------------
    def begin_intent(
        self, request: ProvisionRequest, *, provider: str
    ) -> tuple[IntentRecord, bool]:
        """Persist the intent, or return the existing one. ``(record, created)``."""

        digest = request.digest()
        with self._tx() as db:
            row = db.execute(
                "SELECT * FROM intents WHERE campaign_id = ? AND intent_id = ?",
                (request.campaign_id, request.intent_id),
            ).fetchone()
            if row is not None:
                if row["request_digest"] != digest or row["provider"] != provider:
                    raise ComputeError(
                        operation="provision",
                        failed="intent_id already used for a different request",
                        execution=Execution.NOT_EXECUTED,
                        resources_may_remain=False,
                        retry_safe=False,
                        next_action="use a new intent_id for a different request",
                    )
                return _intent(row), False
            db.execute(
                "INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request.campaign_id,
                    request.intent_id,
                    request.tenant,
                    request.miner,
                    provider,
                    digest,
                    new_ownership_tag(),
                    IntentState.REQUESTED,
                    self.clock(),
                    request.deadline_at,
                    request.spec.storage_gb,
                    request.spec.storage_usd_per_gb_month,
                    request.spec.max_rate_usd_per_hr,
                    None,
                ),
            )
            row = db.execute(
                "SELECT * FROM intents WHERE campaign_id = ? AND intent_id = ?",
                (request.campaign_id, request.intent_id),
            ).fetchone()
            return _intent(row), True

    def intent(self, campaign_id: str, intent_id: str) -> IntentRecord | None:
        row = self._db.execute(
            "SELECT * FROM intents WHERE campaign_id = ? AND intent_id = ?",
            (campaign_id, intent_id),
        ).fetchone()
        return None if row is None else _intent(row)

    def intent_by_tag(self, tag: str) -> IntentRecord | None:
        row = self._db.execute(
            "SELECT * FROM intents WHERE ownership_tag = ?", (tag,)
        ).fetchone()
        return None if row is None else _intent(row)

    def intents(self, *states: IntentState) -> list[IntentRecord]:
        rows = self._db.execute("SELECT * FROM intents ORDER BY created_at").fetchall()
        found = [_intent(row) for row in rows]
        return [item for item in found if not states or item.state in states]

    def set_intent_state(
        self,
        campaign_id: str,
        intent_id: str,
        state: IntentState,
        *,
        offer_usd_per_hr: float | None = None,
    ) -> None:
        with self._tx() as db:
            db.execute(
                "UPDATE intents SET state = ?, "
                "offer_usd_per_hr = COALESCE(?, offer_usd_per_hr) "
                "WHERE campaign_id = ? AND intent_id = ?",
                (state, offer_usd_per_hr, campaign_id, intent_id),
            )

    # resources ----------------------------------------------------------
    def bind_resource(
        self,
        intent: IntentRecord,
        resource_id: str,
        *,
        rate_usd_per_hr: float | None,
        discovered_via: str,
    ) -> ResourceRecord:
        now = self.clock()
        with self._tx() as db:
            existing = db.execute(
                "SELECT * FROM resources WHERE provider = ? AND resource_id = ?",
                (intent.provider, resource_id),
            ).fetchone()
            if existing is None:
                primary = db.execute(
                    "SELECT 1 FROM resources WHERE campaign_id = ? AND intent_id = ? "
                    "AND role = 'primary'",
                    (intent.campaign_id, intent.intent_id),
                ).fetchone()
                db.execute(
                    "INSERT INTO resources VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        intent.provider,
                        resource_id,
                        intent.campaign_id,
                        intent.intent_id,
                        "duplicate" if primary else "primary",
                        ResourceState.STARTING,
                        rate_usd_per_hr,
                        discovered_via,
                        now,
                    ),
                )
                db.execute(
                    "INSERT INTO state_events (provider, resource_id, state, at) "
                    "VALUES (?,?,?,?)",
                    (intent.provider, resource_id, ResourceState.STARTING, now),
                )
            db.execute(
                "UPDATE intents SET state = ? WHERE campaign_id = ? AND intent_id = ?",
                (IntentState.BOUND, intent.campaign_id, intent.intent_id),
            )
            row = db.execute(
                "SELECT * FROM resources WHERE provider = ? AND resource_id = ?",
                (intent.provider, resource_id),
            ).fetchone()
        return _resource(row)

    def resources(
        self, campaign_id: str | None = None, intent_id: str | None = None
    ) -> list[ResourceRecord]:
        rows = self._db.execute(
            "SELECT * FROM resources ORDER BY recorded_at, resource_id"
        ).fetchall()
        return [
            _resource(row)
            for row in rows
            if (campaign_id is None or row["campaign_id"] == campaign_id)
            and (intent_id is None or row["intent_id"] == intent_id)
        ]

    def resource(self, provider: str, resource_id: str) -> ResourceRecord | None:
        row = self._db.execute(
            "SELECT * FROM resources WHERE provider = ? AND resource_id = ?",
            (provider, resource_id),
        ).fetchone()
        return None if row is None else _resource(row)

    def set_resource_state(
        self, provider: str, resource_id: str, state: ResourceState
    ) -> None:
        current = self.resource(provider, resource_id)
        if current is None or current.state == state:
            return
        with self._tx() as db:
            db.execute(
                "UPDATE resources SET state = ? WHERE provider = ? AND resource_id = ?",
                (state, provider, resource_id),
            )
            db.execute(
                "INSERT INTO state_events (provider, resource_id, state, at) "
                "VALUES (?,?,?,?)",
                (provider, resource_id, state, self.clock()),
            )

    def state_events(self, provider: str, resource_id: str) -> list[tuple[str, float]]:
        rows = self._db.execute(
            "SELECT state, at FROM state_events WHERE provider = ? AND resource_id = ? "
            "ORDER BY seq",
            (provider, resource_id),
        ).fetchall()
        return [(row["state"], row["at"]) for row in rows]

    def owned(
        self, campaign_id: str, intent_id: str, resource_id: str
    ) -> CarbonOwnedResource:
        """Issue the ownership handle - only for a resource bound to this campaign's intent."""

        row = self._db.execute(
            "SELECT r.provider, r.resource_id, i.ownership_tag FROM resources r "
            "JOIN intents i ON i.campaign_id = r.campaign_id AND i.intent_id = r.intent_id "
            "WHERE r.campaign_id = ? AND r.intent_id = ? AND r.resource_id = ?",
            (campaign_id, intent_id, resource_id),
        ).fetchone()
        if row is None:
            raise ComputeError(
                operation="ownership",
                failed="resource is not bound to a Carbon intent for this campaign",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="only Carbon-provisioned resources of this campaign "
                "can be stopped or terminated",
            )
        return CarbonOwnedResource(
            provider=row["provider"],
            campaign_id=campaign_id,
            intent_id=intent_id,
            resource_id=row["resource_id"],
            ownership_tag=row["ownership_tag"],
            _issuer=_STORE_ISSUED,
        )

    # charges ------------------------------------------------------------
    def record_provider_charge(
        self, provider: str, resource_id: str, amount_usd: float, basis: str
    ) -> None:
        with self._tx() as db:
            db.execute(
                "INSERT INTO provider_charges VALUES (?,?,?,?,?) ON CONFLICT "
                "(provider, resource_id, basis) DO UPDATE SET "
                "amount_usd = excluded.amount_usd, observed_at = excluded.observed_at",
                (provider, resource_id, amount_usd, basis, self.clock()),
            )

    def provider_charges(self, provider: str, resource_id: str) -> list[float]:
        rows = self._db.execute(
            "SELECT amount_usd FROM provider_charges WHERE provider = ? AND resource_id = ?",
            (provider, resource_id),
        ).fetchall()
        return [row["amount_usd"] for row in rows]


def _intent(row: sqlite3.Row) -> IntentRecord:
    values = dict(row)
    values["state"] = IntentState(values["state"])
    return IntentRecord(**values)


def _resource(row: sqlite3.Row) -> ResourceRecord:
    values = dict(row)
    values["state"] = ResourceState(values["state"])
    return ResourceRecord(**values)
