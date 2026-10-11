"""Prospective development budget registration and shared arm accounting.

The registration is a comparison input, not measured buyer spend. Consumers
must use the same cap for direct, model, and ordinary-surrogate arms. No solver
is called here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass

SCHEMA = "carbon.design-search.equal-budget-registration.v1"
REGISTRATION_ID = "EQUAL-BUDGET-V1"
CHALLENGES = ("battery-v3", "motor", "f02", "f13")
TIERS = ("half", "base", "double")
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


class BudgetRegistrationError(ValueError):
    """A budget is malformed, unregistered, or exceeded."""


def _digest(body):
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seal(body):
    """Return a digest-bound prospective registration body."""
    if type(body) is not dict or "registration_digest" in body:
        raise BudgetRegistrationError("unsealed registration body required")
    return {**body, "registration_digest": _digest(body)}


def _positive_number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise BudgetRegistrationError(f"positive finite {label} required")
    return float(value)


@dataclass(frozen=True)
class BudgetCap:
    solver_evaluations: int
    wall_s: float
    core_s: float

    def __post_init__(self):
        if type(self.solver_evaluations) is not int or self.solver_evaluations <= 0:
            raise BudgetRegistrationError("positive solver-evaluation cap required")
        _positive_number(self.wall_s, "wall cap")
        _positive_number(self.core_s, "core cap")

    @property
    def time_compute(self):
        return {"wall_s": self.wall_s, "core_s": self.core_s}


def _cap(raw, label):
    if type(raw) is not dict or set(raw) != {
        "solver_evaluations",
        "wall_s",
        "core_s",
    }:
        raise BudgetRegistrationError(f"{label} requires evaluations, wall and core")
    count = raw["solver_evaluations"]
    if type(count) is not int or count <= 0:
        raise BudgetRegistrationError(f"positive integer {label} evaluations required")
    return BudgetCap(
        count,
        _positive_number(raw["wall_s"], f"{label} wall seconds"),
        _positive_number(raw["core_s"], f"{label} core seconds"),
    )


def _tiers(raw, label):
    if type(raw) is not dict or set(raw) != set(TIERS):
        raise BudgetRegistrationError(f"{label} needs half/base/double tiers")
    tiers = {tier: _cap(raw[tier], f"{label} {tier}") for tier in TIERS}
    low, base, high = (tiers[tier] for tier in TIERS)
    if (
        low.solver_evaluations != math.ceil(base.solver_evaluations / 2)
        or high.solver_evaluations != 2 * base.solver_evaluations
        or low.wall_s != base.wall_s / 2
        or high.wall_s != base.wall_s * 2
        or low.core_s != base.core_s / 2
        or high.core_s != base.core_s * 2
    ):
        raise BudgetRegistrationError(f"{label} sensitivity tiers must be 1/2/2x")
    return tiers


@dataclass(frozen=True)
class RegisteredBudgets:
    registration_id: str
    registration_digest: str
    challenges: dict[str, dict[str, BudgetCap]]

    def cap(self, challenge, tier):
        if challenge not in self.challenges or tier not in TIERS:
            raise BudgetRegistrationError("unregistered Challenge or budget tier")
        return self.challenges[challenge][tier]


def validate(raw):
    """Validate the closed, self-digested four-Challenge registration."""
    if type(raw) is not dict or set(raw) != {
        "schema",
        "registration_id",
        "authority",
        "evidence_scope",
        "challenge_budgets",
        "registration_digest",
    }:
        raise BudgetRegistrationError("closed budget registration required")
    if raw["schema"] != SCHEMA or raw["registration_id"] != REGISTRATION_ID:
        raise BudgetRegistrationError("unsupported budget registration version")
    if raw["evidence_scope"] != "DEVELOPMENT":
        raise BudgetRegistrationError("development registration required")
    if not isinstance(raw["authority"], str) or not raw["authority"]:
        raise BudgetRegistrationError("Test Lead authority record required")
    if raw["registration_digest"] != _digest(
        {key: value for key, value in raw.items() if key != "registration_digest"}
    ):
        raise BudgetRegistrationError("budget registration digest mismatch")
    rows = raw["challenge_budgets"]
    if type(rows) is not dict or set(rows) != set(CHALLENGES):
        raise BudgetRegistrationError("all four Challenge budgets required")
    parsed = {}
    for challenge in CHALLENGES:
        row = rows[challenge]
        if type(row) is not dict or set(row) != {
            "decision_scope",
            "basis",
            "justification",
            "source_refs",
            "tiers",
        }:
            raise BudgetRegistrationError(f"{challenge} budget provenance incomplete")
        if row["basis"] != "ASSUMPTION":
            raise BudgetRegistrationError(
                "unmeasured buyer budgets must say ASSUMPTION"
            )
        for field in ("decision_scope", "justification"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise BudgetRegistrationError(f"{challenge} {field} required")
        if (
            type(row["source_refs"]) is not list
            or not row["source_refs"]
            or any(not isinstance(ref, str) or not ref for ref in row["source_refs"])
        ):
            raise BudgetRegistrationError(f"{challenge} source anchors required")
        parsed[challenge] = _tiers(row["tiers"], challenge)
    return RegisteredBudgets(raw["registration_id"], raw["registration_digest"], parsed)


def materialize_value_rule(base_rule, registration, challenge):
    """Bind VALUE-BAR-V1's item 5 to one prospective Challenge budget."""
    resolved = validate(registration)
    if (
        type(base_rule) is not dict
        or base_rule.get("rule_id") != "VALUE-BAR-V1"
        or base_rule.get("item_5", {}).get("budget", "missing") is not None
    ):
        raise BudgetRegistrationError("unbudgeted VALUE-BAR-V1 base rule required")
    if challenge not in resolved.challenges:
        raise BudgetRegistrationError("unregistered Challenge")
    rule = copy.deepcopy(base_rule)
    rule["rule_id"] = f"VALUE-BAR-V1:{challenge}:{resolved.registration_id}"
    row = registration["challenge_budgets"][challenge]
    item5 = rule["item_5"]
    item5.update(
        budget=resolved.cap(challenge, "base").time_compute,
        challenge=challenge,
        budget_registration_digest=resolved.registration_digest,
        budget_basis=row["basis"],
        budget_tiers={
            tier: resolved.cap(challenge, tier).time_compute for tier in TIERS
        },
        solver_evaluation_caps={
            tier: resolved.cap(challenge, tier).solver_evaluations for tier in TIERS
        },
    )
    return rule


def validate_rule_tiers(item5):
    """Check a materialized VALUE-BAR-V1 rule's three shared arm caps."""
    if (
        type(item5) is not dict
        or item5.get("budget_basis") != "ASSUMPTION"
        or type(item5.get("solver_evaluation_caps")) is not dict
        or type(item5.get("budget_tiers")) is not dict
    ):
        raise BudgetRegistrationError("tiered rule budget fields required")
    counts = item5["solver_evaluation_caps"]
    budgets = item5["budget_tiers"]
    if set(counts) != set(TIERS) or set(budgets) != set(TIERS):
        raise BudgetRegistrationError("tiered rule needs half/base/double")
    if any(
        type(budgets[tier]) is not dict or set(budgets[tier]) != {"wall_s", "core_s"}
        for tier in TIERS
    ):
        raise BudgetRegistrationError("tiered rule requires wall/core pairs")
    caps = _tiers(
        {tier: {"solver_evaluations": counts[tier], **budgets[tier]} for tier in TIERS},
        "rule",
    )
    if item5.get("budget") != caps["base"].time_compute:
        raise BudgetRegistrationError("base value budget differs from registration")
    return caps


class BudgetLedger:
    """The same hard attempt/time/compute accounting for every arm."""

    def __init__(self, cap):
        if not isinstance(cap, BudgetCap):
            raise BudgetRegistrationError("validated BudgetCap required")
        self.cap = cap
        self.solver_evaluations = 0
        self.wall_s = 0.0
        self.core_s = 0.0

    def _fits(self, cost, *, solver_attempt):
        if type(cost) is not dict or set(cost) != {"wall_s", "core_s"}:
            raise BudgetRegistrationError("complete wall/core cost required")
        wall, core = cost["wall_s"], cost["core_s"]
        for amount, unit in ((wall, "wall"), (core, "core")):
            if type(amount) not in (int, float) or not math.isfinite(amount):
                raise BudgetRegistrationError(f"finite numeric {unit} charge required")
            if amount < 0 or (solver_attempt and amount == 0):
                raise BudgetRegistrationError(f"positive {unit} solve charge required")
        return (
            (
                not solver_attempt
                or self.solver_evaluations < self.cap.solver_evaluations
            )
            and self.wall_s + wall <= self.cap.wall_s + 1e-12
            and self.core_s + core <= self.cap.core_s + 1e-12
        )

    def charge_overhead(self, cost):
        if not self._fits(cost, solver_attempt=False):
            return False
        self.wall_s += cost["wall_s"]
        self.core_s += cost["core_s"]
        return True

    def charge_solver_attempt(self, planning_bound, actual_cost):
        if not self._fits(planning_bound, solver_attempt=True):
            return False
        if type(actual_cost) is not dict or set(actual_cost) != {"wall_s", "core_s"}:
            raise BudgetRegistrationError("actual complete-panel cost required")
        for unit in ("wall_s", "core_s"):
            _positive_number(actual_cost[unit], f"actual {unit}")
        self.wall_s += actual_cost["wall_s"]
        self.core_s += actual_cost["core_s"]
        self.solver_evaluations += 1
        if any(
            actual_cost[unit] > planning_bound[unit] for unit in ("wall_s", "core_s")
        ):
            raise BudgetRegistrationError("planning bound below actual cost")
        return True
