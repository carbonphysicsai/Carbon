"""Measuring the same-miner self-improvement factor (VALIDATOR-14 §7;
OWNER-TESTNET-WEIGHTS-01 §3).

The owner's rule: a miner beating its own winner must clear a factor large
enough that "copy it and change one thing" does not succeed. That factor is
measured here, never guessed:
1. take a winning construction;
2. generate every one-step change of one parameter (`neighbours`, in the
   Challenge contract's own vocabulary);
3. score each against the original on the same fresh cases (`evaluate`
   returns per-case errors, lower is better);
4. report the distribution of the apparent relative improvement,
   `(mean_original - mean_variant) / mean_original`, and propose a factor
   above its upper tail.

The result is a proposal, `PROPOSED_NOT_ADOPTED`: the owner adopts the factor
as a new weight-policy version. Use development cases only, never a sealed
set.
"""

from __future__ import annotations

import copy
import math

SCHEMA = "carbon.rewards.self-improvement-study.v1"


def one_step_neighbours(strategy, surfaces):
    """`(change, variant)` for every one-step change of one parameter.
    `surfaces` maps a parameter to `("uint", lo, hi)`, `("float", lo, hi,
    step_ratio)` or `("choice", options)`.
    - **uint:** ±1, inside the range.
    - **float:** multiplied or divided by `step_ratio`, inside the range.
    - **choice:** each other option.
    """
    parameters = strategy.get("parameters", {})
    found = []
    for name in sorted(parameters):
        if name not in surfaces:
            continue
        value, surface = parameters[name], surfaces[name]
        if surface[0] == "uint":
            _, lo, hi = surface
            options = [v for v in (value - 1, value + 1) if lo <= v <= hi]
        elif surface[0] == "float":
            _, lo, hi, ratio = surface
            options = [v for v in (value / ratio, value * ratio) if lo <= v <= hi]
        elif surface[0] == "choice":
            options = [v for v in surface[1] if v != value]
        else:
            raise ValueError("unknown surface kind")
        for option in options:
            variant = copy.deepcopy(strategy)
            variant["parameters"][name] = option
            found.append((f"{name}={option!r}", variant))
    return found


def study(strategy, neighbours, evaluate, *, margin=0.0):
    """The measured distribution and a proposed factor.

    The proposal is the largest apparent improvement any one-step change
    achieved, plus `margin`, and never below 0. A same-miner promotion would
    have to exceed it."""
    base = evaluate(strategy)
    rows = []
    for change, variant in neighbours:
        errors = evaluate(variant)
        ids = sorted(set(base) & set(errors))
        if not ids:
            rows.append({"change": change, "n": 0, "relative_improvement": None})
            continue
        before = math.fsum(base[c] for c in ids) / len(ids)
        after = math.fsum(errors[c] for c in ids) / len(ids)
        rows.append(
            {
                "change": change,
                "n": len(ids),
                "relative_improvement": (before - after) / before if before else None,
            }
        )
    measured = sorted(
        r["relative_improvement"] for r in rows if r["relative_improvement"] is not None
    )
    upper = measured[-1] if measured else None
    return {
        "schema": SCHEMA,
        "status": "PROPOSED_NOT_ADOPTED",
        "n_neighbours": len(rows),
        "rows": rows,
        "max_apparent_improvement": upper,
        "median_apparent_improvement": (
            measured[len(measured) // 2] if measured else None
        ),
        "margin": margin,
        "proposed_factor": None if upper is None else max(0.0, upper) + margin,
    }
