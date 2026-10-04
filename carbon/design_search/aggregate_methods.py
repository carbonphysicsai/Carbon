"""Challenge-neutral search extension for cross-condition aggregate objectives.

The established methods use the worst individual condition objective. Some
Challenge contracts instead define a lexicographic objective from different
conditions, such as maximum ripple followed by minimum mean torque. This
module keeps the registered screen/confirm query pattern while requiring the
Challenge adapter to supply that aggregate explicitly.
"""

from __future__ import annotations


def _point(design, condition):
    return (*design, *condition)


def screen_then_confirm(view, oracle, *, screen_condition, aggregate_objective):
    """Screen, then fully confirm every feasible candidate that fits budget.

    No single-condition early-pruning bound is assumed because the supplied
    cross-condition aggregate may not be bounded by the screen objective.
    """

    if not callable(aggregate_objective):
        raise TypeError("aggregate_objective_required")
    screen = view.conditions[screen_condition]
    rest = [
        condition
        for index, condition in enumerate(view.conditions)
        if index != screen_condition
    ]
    reach = view.designs[: max(0, oracle.budget - oracle.used)]
    screened = (
        oracle.query([_point(design, screen) for design in reach]) if reach else []
    )
    screened_by_design = dict(zip(reach, screened))
    candidates = sorted(
        (view.objective(row), design)
        for design, row in zip(reach, screened)
        if view.passes(row)
    )
    best = None
    for _screen_objective, design in candidates:
        if oracle.used + len(rest) > oracle.budget:
            break
        confirmed = (
            oracle.query([_point(design, condition) for condition in rest])
            if rest
            else []
        )
        if all(view.passes(row) for row in confirmed):
            key = (
                aggregate_objective([screened_by_design[design], *confirmed]),
                design,
            )
            best = key if best is None or key < best else best
    return [] if best is None else [view.select_design(best[1], best[0])]
