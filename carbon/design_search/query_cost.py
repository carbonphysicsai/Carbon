"""Optional measured cost ledger for counted design-optimizer attempts.

The deterministic query budget is independent of elapsed cost. A producer
supplies the hardware route and allocated core count; no rate or solver/query
exchange is invented. Every attempted query receives exactly one charge,
including invalid proposals and model failures.
"""

from __future__ import annotations

import math

from carbon.design_search import cost

KINDS = ("MODEL_OK", "MODEL_FAILED", "INVALID")


class QueryCostRecorder:
    def __init__(self, ledger, *, arm, route, allocated_cores):
        if not isinstance(ledger, cost.Ledger):
            raise cost.CostError("query_cost_ledger_required")
        if type(arm) is not str or not arm or arm == cost.VERIFICATION:
            raise cost.CostError("query_cost_arm_required")
        if type(route) is not str or not route:
            raise cost.CostError("query_cost_route_required")
        if (
            type(allocated_cores) not in (int, float)
            or not math.isfinite(allocated_cores)
            or allocated_cores <= 0
        ):
            raise cost.CostError("positive_allocated_cores_required")
        self.ledger = ledger
        self.arm = arm
        self.route = route
        self.allocated_cores = allocated_cores
        self.counts = {kind: 0 for kind in KINDS}
        self._charges = []

    def record(self, kind, *, wall_seconds):
        if kind not in KINDS:
            raise cost.CostError("unknown_query_cost_kind")
        if (
            type(wall_seconds) not in (int, float)
            or not math.isfinite(wall_seconds)
            or wall_seconds < 0
        ):
            raise cost.CostError("non_negative_wall_seconds_required")
        charge = cost.Charge(
            arm=self.arm,
            category="query_validation" if kind == "INVALID" else "inference",
            route=self.route,
            core_seconds=wall_seconds * self.allocated_cores,
            basis="ALLOCATED_CPU_X_WALL",
            note=kind,
        )
        self.ledger.add(charge)
        self._charges.append(charge)
        self.counts[kind] += 1

    def reconcile(self, accounting):
        """Refuse an apparently complete cost ledger missing any attempt."""
        if (
            sum(self.counts.values()) != accounting["attempted_queries"]
            or self.counts["INVALID"] != accounting["invalid_queries"]
            or self.counts["MODEL_FAILED"] != accounting["model_failures"]
        ):
            raise cost.CostError("query_cost_accounting_mismatch")
        return {
            "attempted_queries": sum(self.counts.values()),
            "charged_core_seconds": sum(
                charge.core_seconds for charge in self._charges
            ),
            "route": self.route,
            "basis": "ALLOCATED_CPU_X_WALL",
        }
