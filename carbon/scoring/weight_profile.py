"""Versioned DEVELOPMENT weight profiles that may give a leg zero weight.

The core Score Pack (`pack.py`) requires three strictly positive weights,
and it stays that way. This separate contract,
`carbon.development-weight-profile.v1`, lets a DEVELOPMENT experiment test
profiles such as 0/30/70 without weakening that parser or substituting a
constant "perfect" component.

Semantics:
- The legs are exactly physics, robustness and accuracy. Each weight is a
  decimal in [0, 1], and the positive weights sum to exactly 1 (decimal
  arithmetic). An all-zero profile is refused.
- A zero weight removes that leg from the ranking arithmetic: its term is
  omitted before any logarithm. It does **not** remove mandatory gates,
  required measurements or critical-region protections. Callers apply
  those before combining, and a gate failure is never rescued here.
- A positive-weight leg must have a measured score in [0, 1]. A missing one
  is refused (`missing_component`), never coerced. A measured score of
  exactly 0 gives a combined score of 0, as in A5.
- The arithmetic is A5's weighted geometric mean in log space, with ordered
  `fsum`, over the positive-weight legs only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .engine import (
    ScoringComputationError,
    _finite,
    _ordered_fsum,
    _unit_interval,
)

SCHEMA = "carbon.development-weight-profile.v1"
LEGS = ("physics", "robustness", "accuracy")


class WeightProfileError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class WeightProfile:
    profile_id: str
    weights: tuple  # (physics, robustness, accuracy) as Decimal

    @property
    def positive(self):
        return tuple(leg for leg, w in zip(LEGS, self.weights, strict=True) if w > 0)

    def document(self):
        return {
            "schema": SCHEMA,
            "id": self.profile_id,
            "weights": {leg: str(w) for leg, w in zip(LEGS, self.weights, strict=True)},
        }


def parse(document):
    """Validate one profile: {"id": ..., "weights": {physics, robustness, accuracy}}."""
    if type(document) is not dict or set(document) - {"id", "weights", "rationale"}:
        raise WeightProfileError("profile_fields")
    profile_id = document.get("id")
    if type(profile_id) is not str or not 1 <= len(profile_id) <= 64:
        raise WeightProfileError("profile_id")
    weights = document.get("weights")
    if type(weights) is not dict or set(weights) != set(LEGS):
        raise WeightProfileError("weight_legs", "exactly physics, robustness, accuracy")
    parsed = []
    for leg in LEGS:
        value = weights[leg]
        if type(value) not in (int, float, str) or type(value) is bool:
            raise WeightProfileError("weight_type", leg)
        try:
            decimal = Decimal(str(value))
        except InvalidOperation:
            raise WeightProfileError("weight_type", leg) from None
        if not decimal.is_finite() or decimal < 0 or decimal > 1:
            raise WeightProfileError("weight_range", leg)
        parsed.append(decimal)
    if all(w == 0 for w in parsed):
        raise WeightProfileError("all_zero")
    if sum(parsed) != 1:
        raise WeightProfileError("weight_sum", "positive weights must sum to exactly 1")
    return WeightProfile(profile_id, tuple(parsed))


def combine(profile, components):
    """The profile's combined score from measured leg scores in [0, 1].

    `components` maps leg to a score or None. A positive-weight leg must be
    measured; a zero-weight leg is ignored whether or not it is measured.
    """
    if type(profile) is not WeightProfile:
        raise TypeError("a parsed WeightProfile is required")
    scores = []
    for leg in profile.positive:
        value = components.get(leg)
        if value is None:
            raise WeightProfileError("missing_component", leg)
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise WeightProfileError("component_range", leg)
        scores.append((leg, value))
    if any(value == 0.0 for _, value in scores):
        return 0.0
    terms = []
    for leg, value in scores:
        weight = float(profile.weights[LEGS.index(leg)])
        logarithm = _finite(math.log(value), "log term")
        term = _finite(weight * logarithm, "weighted log term")
        if term > 0.0:
            raise ScoringComputationError("scoring.range", "positive log term")
        terms.append(term)
    log_sum = _ordered_fsum(tuple(terms), "profile ordered log sum")
    return _unit_interval(math.exp(log_sum), "profile combined score")
