"""Compute-cost accounting for Track B design-search arms (TRACK-B-HARNESS-01).

OWNER-GRAPHITE-TEST-WAVE-01 §5: money is the unit. A cost is measured or
allocated core-seconds on a named hardware route, priced in USD only at an
approved rate for that route. No rate is approved in the repository yet, so a
view is priced in core-seconds when every charge shares one route, through a
declared paired-timing conversion when one is cited, and is otherwise
UNPRICED_MIXED_HARDWARE. No exchange rate between a solver run and a model
query is ever assumed.

Every charge names its arm and category. Verification of committed proposals
is charged to the separate ``VERIFICATION`` line, never to an arm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: One-time costs: amortised over a decision count in the economic view and
#: excluded from the alignment view.
ONE_TIME = ("training_data_generation", "fitting")
#: Per-decision costs.
PER_DECISION = ("inference", "in_search_solve", "cache_lookup", "fallback")
CATEGORIES = ONE_TIME + PER_DECISION + ("verification",)
BASES = ("MEASURED_CPU", "ALLOCATED_CPU_X_WALL")
VERIFICATION = "VERIFICATION"

PRICED_USD = "PRICED_USD"
SINGLE_ROUTE = "CORE_SECONDS_SINGLE_ROUTE"
CONVERTED = "CONVERTED_BY_PAIRED_TIMING"
UNPRICED = "UNPRICED_MIXED_HARDWARE"
NO_APPROVED_RATE = "NO_APPROVED_RATE"


class CostError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class Charge:
    """One cost: core-seconds on one hardware route."""

    arm: str
    category: str
    route: str
    core_seconds: float
    basis: str
    note: str = ""

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise CostError("unknown_cost_category", self.category)
        if self.basis not in BASES:
            raise CostError("unknown_cost_basis", self.basis)
        if (self.category == "verification") != (self.arm == VERIFICATION):
            raise CostError("verification_is_charged_to_no_arm", self.arm)
        if type(self.route) is not str or not self.route:
            raise CostError("cost_route_required")
        value = self.core_seconds
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise CostError("core_seconds_not_finite_non_negative", repr(value))

    def as_dict(self):
        return {
            "arm": self.arm,
            "category": self.category,
            "route": self.route,
            "core_seconds": self.core_seconds,
            "basis": self.basis,
            "note": self.note,
        }


@dataclass(frozen=True)
class Rate:
    """An approved USD rate for one route, citing its approval."""

    route: str
    usd_per_core_hour: float
    approval: str


@dataclass(frozen=True)
class Conversion:
    """Core-seconds on ``source`` count as ``factor`` x core-seconds on
    ``target``, from cited paired timing of the same cases on both routes."""

    source: str
    target: str
    factor: float
    evidence: str


@dataclass(frozen=True)
class Unit:
    """What a budget and a view are expressed in: USD, or core-seconds on one
    target route."""

    kind: str  # "usd" or "core_seconds"
    route: str | None = None

    def __post_init__(self):
        if self.kind not in ("usd", "core_seconds"):
            raise CostError("unknown_cost_unit", self.kind)
        if (self.kind == "core_seconds") != (self.route is not None):
            raise CostError("core_seconds_unit_names_one_route")

    def as_dict(self):
        return {"kind": self.kind, "route": self.route}


class Ledger:
    """Append-only charges for one study."""

    def __init__(self):
        self._charges = []

    def add(self, charge):
        if not isinstance(charge, Charge):
            raise CostError("charge_required")
        self._charges.append(charge)
        return charge

    def charges(self, arm=None, categories=None):
        return [
            c
            for c in self._charges
            if (arm is None or c.arm == arm)
            and (categories is None or c.category in categories)
        ]

    def as_list(self):
        return [c.as_dict() for c in self._charges]


def price(charges, unit, *, rates=(), conversions=()):
    """The total of ``charges`` in ``unit``, or why it cannot be priced.

    Returns ``{"status", "value", "unit", "basis"}``. ``value`` is None unless
    every charge converts into ``unit``.
    """

    charges = list(charges)
    rates = {r.route: r for r in rates}
    if unit.kind == "usd":
        missing = sorted({c.route for c in charges if c.route not in rates})
        if missing:
            return {
                "status": NO_APPROVED_RATE,
                "value": None,
                "unit": unit.as_dict(),
                "basis": {"routes_without_approved_rate": missing},
            }
        value = sum(
            c.core_seconds / 3600 * rates[c.route].usd_per_core_hour for c in charges
        )
        return {
            "status": PRICED_USD,
            "value": value,
            "unit": unit.as_dict(),
            "basis": {"rates": sorted({rates[c.route].approval for c in charges})},
        }
    factors = {(c.source, c.target): c for c in conversions}
    total = 0.0
    used = set()
    for charge in charges:
        if charge.route == unit.route:
            total += charge.core_seconds
            continue
        conversion = factors.get((charge.route, unit.route))
        if conversion is None:
            return {
                "status": UNPRICED,
                "value": None,
                "unit": unit.as_dict(),
                "basis": {"unconverted_route": charge.route},
            }
        total += charge.core_seconds * conversion.factor
        used.add(conversion.evidence)
    return {
        "status": CONVERTED if used else SINGLE_ROUTE,
        "value": total,
        "unit": unit.as_dict(),
        "basis": {"conversions": sorted(used)},
    }


def amount(charges, unit, *, rates=(), conversions=()):
    """``price(...)["value"]``, refusing an unpriceable total."""

    priced = price(charges, unit, rates=rates, conversions=conversions)
    if priced["value"] is None:
        raise CostError("charges_not_priceable_in_unit", priced["status"])
    return priced["value"]
