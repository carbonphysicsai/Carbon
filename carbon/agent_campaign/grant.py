"""The owner's spending grant: no grant, no dispatch.

Handoff §15: before paid execution, bind the provider/account, permitted runs,
expiry, monetary ceiling, compute limits and cleanup allowance in a grant. Every
value is the owner's (live economics are human-reserved, AGENTS.md §3); this
module invents none. A document with any missing or `HUMAN_INPUT` value is
refused, and the controller cannot dispatch without a grant whose provider
matches its adapter.

`worst_case_run_cost` is what the controller reserves before each launch. The
controller dispatches only while settled + reserved + the next reservation +
the cleanup allowance stays within the ceiling.

A zero-spend grant (every amount 0, 0 runs, 0 submissions; `zero_spend`) binds
only a dedicated admission controller's identity
(A4-DEDICATED-ADMISSION-CONTROLLERS-01). Everything that could spend refuses it
first (`grant_is_zero_spend`).

A grant is a maintainer-held file. This module checks its shape and binding; it
does not authenticate who wrote it.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from decimal import Decimal

from .provider import identifier, money

SCHEMA = "carbon.agent-campaign.spending-grant.v1"
FIELDS = (
    "schema",
    "grant_id",
    "provider",
    "account",
    "granted_by",
    "expires_at",
    "currency",
    "monetary_ceiling",
    "cleanup_allowance",
    "worst_case_run_cost",
    "permitted_runs",
    "max_concurrency",
    "max_runtime_s",
    "max_submissions",
)
#: Optional fields: absent, the grant is exactly as before (its document and
#: digest unchanged). `pod_rate_ceiling_usd_per_hr` (GRANT-POD-CEILING-01) is
#: the most a pod under the grant may cost an hour; absent, pod_control's
#: constant applies.
OPTIONAL_FIELDS = ("pod_rate_ceiling_usd_per_hr",)
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class GrantError(ValueError):
    """The grant cannot authorize dispatch."""


def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise GrantError(name + " is a positive integer")
    return value


@dataclass(frozen=True)
class SpendingGrant:
    grant_id: str
    provider: str
    account: str
    granted_by: str
    expires_at: datetime.datetime
    currency: str
    monetary_ceiling: Decimal
    cleanup_allowance: Decimal
    worst_case_run_cost: Decimal
    permitted_runs: int
    max_concurrency: int
    max_runtime_s: int
    max_submissions: int
    pod_rate_ceiling_usd_per_hr: Decimal | None = None

    @classmethod
    def from_document(cls, document):
        if type(document) is not dict or not (
            set(FIELDS) <= set(document) <= set(FIELDS) | set(OPTIONAL_FIELDS)
        ):
            raise GrantError("grant_exact_fields_required")
        ceiling = document.get("pod_rate_ceiling_usd_per_hr")
        if "pod_rate_ceiling_usd_per_hr" in document:
            try:
                ceiling = money(ceiling)
            except ValueError as error:
                raise GrantError(str(error)) from None
            if ceiling <= 0:
                raise GrantError("pod_rate_ceiling_usd_per_hr must be positive")
        if document["schema"] != SCHEMA:
            raise GrantError("grant_schema")
        if any(v in (None, "HUMAN_INPUT", "TODO", "") for v in document.values()):
            raise GrantError("grant_value_missing")
        try:
            for name in ("grant_id", "provider", "account", "granted_by", "currency"):
                identifier(document[name], name)
            amounts = {
                name: money(document[name])
                for name in (
                    "monetary_ceiling",
                    "cleanup_allowance",
                    "worst_case_run_cost",
                )
            }
        except ValueError as error:
            raise GrantError(str(error)) from None
        # A zero-spend grant (A4-DEDICATED-ADMISSION-CONTROLLERS-01) is whole
        # or refused: every amount 0, 0 runs and 0 submissions. It authorizes
        # nothing; it only binds a controller that never dispatches.
        zero = not any(amounts.values())
        if zero:
            for name in ("permitted_runs", "max_submissions"):
                if type(document[name]) is not int or document[name] != 0:
                    raise GrantError(
                        "a zero-spend grant permits 0 runs and 0 submissions"
                    )
        elif amounts["worst_case_run_cost"] <= 0:
            raise GrantError("worst_case_run_cost must be positive")
        if (
            amounts["cleanup_allowance"] + amounts["worst_case_run_cost"]
            > amounts["monetary_ceiling"]
        ):
            raise GrantError("the ceiling cannot cover one run and its cleanup")
        if type(document["expires_at"]) is not str or not _TIME.fullmatch(
            document["expires_at"]
        ):
            raise GrantError("expires_at is UTC YYYY-MM-DDTHH:MM:SSZ")
        expires = datetime.datetime.strptime(
            document["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.UTC)
        return cls(
            grant_id=document["grant_id"],
            provider=document["provider"],
            account=document["account"],
            granted_by=document["granted_by"],
            expires_at=expires,
            currency=document["currency"],
            permitted_runs=(
                0 if zero else _positive(document["permitted_runs"], "permitted_runs")
            ),
            max_concurrency=_positive(document["max_concurrency"], "max_concurrency"),
            max_runtime_s=_positive(document["max_runtime_s"], "max_runtime_s"),
            max_submissions=(
                0 if zero else _positive(document["max_submissions"], "max_submissions")
            ),
            **amounts,
            pod_rate_ceiling_usd_per_hr=ceiling,
        )

    @property
    def zero_spend(self):
        """Whether this grant authorizes no spend at all: every amount 0, 0 runs
        and 0 submissions. The controller, the live model and the phase-3
        provider each refuse it before anything is reserved."""
        return (
            not (
                self.monetary_ceiling
                or self.cleanup_allowance
                or self.worst_case_run_cost
            )
            and self.permitted_runs == 0
            and self.max_submissions == 0
        )

    def document(self):
        return {
            "schema": SCHEMA,
            "grant_id": self.grant_id,
            "provider": self.provider,
            "account": self.account,
            "granted_by": self.granted_by,
            "expires_at": self.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "currency": self.currency,
            "monetary_ceiling": str(self.monetary_ceiling),
            "cleanup_allowance": str(self.cleanup_allowance),
            "worst_case_run_cost": str(self.worst_case_run_cost),
            "permitted_runs": self.permitted_runs,
            "max_concurrency": self.max_concurrency,
            "max_runtime_s": self.max_runtime_s,
            "max_submissions": self.max_submissions,
            **(
                {}
                if self.pod_rate_ceiling_usd_per_hr is None
                else {
                    "pod_rate_ceiling_usd_per_hr": str(self.pod_rate_ceiling_usd_per_hr)
                }
            ),
        }


def template(provider):
    """The grant the owner must complete; every value is HUMAN_INPUT."""
    return {
        name: (
            SCHEMA
            if name == "schema"
            else provider if name == "provider" else "HUMAN_INPUT"
        )
        for name in FIELDS
    }
