"""The physics half of the exam, shared by the sealed graders (Validator spec
VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023; owner direction: gates for gross
physical violations, measured fidelity for the degree).

```text
A = mean(A_acc, A_robust, A_law, A_response)      # equal weights, each in 0..1
```

- **A_acc**: the Challenge's own accuracy benefit, unchanged.
- **A_robust**: the same benefit on the worst stratum (near-limit versus interior
  by the reference's own distance to its limits, a median split), so one weak
  region caps it.
- **A_law**: ``1/(1+r)`` where ``r`` is the mean residual of the registered laws
  in the same normalised-output units as A_acc (TRAIN spread), so no new scale is
  chosen.
- **A_response** (local sensitivities from predictions at x and x(1 +- delta))
  needs model queries beyond the bank cells. Those queries run in the shared
  producer, which this module does not touch, so this version registers
  ``legs_not_applied: ["A_response"]`` and averages the applied legs only. The
  definition says so; nothing here pretends it was measured.

Laws are plugin data: each constrains a predicted row and names the output that
normalises its residual. A law that the reference satisfies with a clear margin
may also gate gross violation; the gate tolerance is ``reference residual
quantile + a registered margin`` (PHYSICS-CONTRACT-01). The margin is a registered
value this module does not choose: a law whose margin is None is measured but does
not gate.

Pure arithmetic; no I/O. DEVELOPMENT only: no qualification, weight, reward or
LIVE authority.
"""

from __future__ import annotations

import math
from statistics import fmean

RULE = "A=mean(A_acc,A_robust,A_law)"
LEGS = ("A_acc", "A_robust", "A_law")
NOT_APPLIED = ("A_response",)
SCHEMA = "carbon.scoring.physics-half.v1"
ROBUST = "median_split_by_reference_limit_distance"


class PhysicsHalfRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise PhysicsHalfRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def block(laws):
    """The definition block. ``laws``: ``[(name, role, normaliser_output,
    gate_margin)]`` with role ``measured`` or ``gate`` and ``gate_margin`` None
    until the Validator registers it."""
    return {
        "schema": SCHEMA,
        "rule": RULE,
        "legs": list(LEGS),
        "legs_not_applied": list(NOT_APPLIED),
        "robust": ROBUST,
        "laws": [
            {"name": n, "role": r, "normaliser": o, "gate_margin": g}
            for n, r, o, g in laws
        ],
    }


def validate_block(value):
    _require(
        type(value) is dict
        and set(value)
        == {"schema", "rule", "legs", "legs_not_applied", "robust", "laws"}
        and value["schema"] == SCHEMA
        and value["rule"] == RULE
        and value["legs"] == list(LEGS)
        and value["legs_not_applied"] == list(NOT_APPLIED)
        and value["robust"] == ROBUST
        and type(value["laws"]) is list
        and all(
            type(law) is dict
            and set(law) == {"name", "role", "normaliser", "gate_margin"}
            and law["role"] in ("measured", "gate")
            and type(law["name"]) is str
            and type(law["normaliser"]) is str
            and (law["gate_margin"] is None or _number(law["gate_margin"]))
            for law in value["laws"]
        ),
        "physics_block",
    )
    return value


def acc_benefit(errors):
    """The accuracy benefit of normalised absolute errors ``errors`` (rows x
    targets): the minimum of 1/(1+loss) over each target mean error and the
    worst row mean error (the Challenge A form)."""
    losses = [fmean(row[j] for row in errors) for j in range(len(errors[0]))]
    losses.append(max(fmean(row) for row in errors))
    return min(1.0 / (1.0 + loss) for loss in losses)


def split_by_nearness(nearness):
    """Indices of the nearer half and the interior half (stable on ties); one
    stratum only when there is a single row."""
    order = sorted(range(len(nearness)), key=lambda i: (nearness[i], i))
    half = max(1, len(order) // 2)
    near, interior = order[:half], order[half:]
    return [sorted(near)] + ([sorted(interior)] if interior else [])


def robust_benefit(errors, strata):
    """The worst stratum accuracy benefit."""
    return min(acc_benefit([errors[i] for i in stratum]) for stratum in strata)


def law_benefit(residuals):
    """``(A_law, record)`` from ``{law name: [normalised residual per row]}``."""
    means = {name: fmean(rows) for name, rows in residuals.items()}
    r = fmean(means.values()) if means else 0.0
    return 1.0 / (1.0 + r), {"mean_residual_by_law": means, "mean_residual": r}


def combine(a_acc, a_robust, a_law):
    legs = {"A_acc": a_acc, "A_robust": a_robust, "A_law": a_law}
    return fmean(legs.values()), legs
