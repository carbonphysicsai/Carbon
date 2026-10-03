"""Carbon's design-search methods: what a method proposal may name.

Graphite's Optimizer researcher proposes a search method as data: a registered
method name and its parameters (`MethodProposal`). Carbon runs only the
methods implemented here, with parameters checked against closed bounds, so a
proposal can change which registered search runs and how, never what code
runs.

Every method works on a Challenge-neutral `View` of one search request:
- `designs` and `conditions` are tuples of variable values, `designs` forming a
  full grid over its variables;
- `passes(q)`, `objective(q)` and `margin(q)` read the Challenge's predicted
  quantities (feasibility, the lower-is-better objective, and the
  band-normalised binding constraint margin);
- `select_design` and `select_point` write a selection in the Challenge's own
  commitment format.

Each method selects by the same rule as the fixed baseline, restricted to
what it queried: PB-INV, the design predicted feasible at every condition
with the lowest worst-case objective, ties by the lower design; PB-ADV, the
predicted-feasible points with the smallest margin, up to the verification
budget, ordered by margin, then design, then condition. A method works
within the oracle's query budget and never asks for more. When its next query
would exceed the budget it stops and selects from what it has.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

PROPOSAL_SCHEMA = "carbon.design-search.method-proposal.v1"
MODES = ("PB-INV", "PB-ADV")


class MethodError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class View:
    mode: str
    designs: tuple
    conditions: tuple
    verification_budget: int
    passes: Callable
    objective: Callable
    margin: Callable
    select_design: Callable
    select_point: Callable


def _point(design, condition):
    return (*design, *condition)


def screen_then_confirm(view, oracle, *, screen_condition):
    """PB-INV. Screen every design at one condition, then confirm the
    screened-feasible designs at the other conditions, lowest screened
    objective first. A design whose screened objective already exceeds the
    best confirmed worst case cannot win, so the search stops there."""
    screen = view.conditions[screen_condition]
    rest = [c for i, c in enumerate(view.conditions) if i != screen_condition]
    reach = view.designs[: max(0, oracle.budget - oracle.used)]
    screened = oracle.query([_point(d, screen) for d in reach]) if reach else []
    candidates = sorted(
        (view.objective(q), d) for d, q in zip(reach, screened) if view.passes(q)
    )
    best = None
    for first, design in candidates:
        if best is not None and first > best[0]:
            break
        if oracle.used + len(rest) > oracle.budget:
            break
        confirmed = oracle.query([_point(design, c) for c in rest]) if rest else []
        if all(view.passes(q) for q in confirmed):
            key = (max([first, *(view.objective(q) for q in confirmed)]), design)
            best = key if best is None or key < best else best
    return [] if best is None else [view.select_design(best[1], best[0])]


def _axes(designs):
    width = len(designs[0])
    axes = [sorted({d[k] for d in designs}) for k in range(width)]
    size = 1
    for axis in axes:
        size *= len(axis)
    if size != len(set(designs)):
        raise MethodError("design_space_is_not_a_grid")
    return axes


def coarse_to_fine(view, oracle, *, stride, radius, top_k):
    """PB-INV or PB-ADV. Query every `stride`-th design on each axis at every
    condition, then the designs within `radius` grid steps of the `top_k`
    best (PB-INV: lowest feasible worst case; PB-ADV: smallest feasible
    margin), and select from everything queried."""
    axes = _axes(view.designs)
    index = {d: tuple(axes[k].index(v) for k, v in enumerate(d)) for d in view.designs}
    evaluated = {}

    def run(designs):
        for design in designs:
            if design in evaluated:
                continue
            if oracle.used + len(view.conditions) > oracle.budget:
                return
            evaluated[design] = oracle.query(
                [_point(design, c) for c in view.conditions]
            )

    def feasible_designs():
        return sorted(
            (max(view.objective(q) for q in qs), d)
            for d, qs in evaluated.items()
            if all(view.passes(q) for q in qs)
        )

    def feasible_points():
        return sorted(
            (view.margin(q), d, c, i)
            for d, qs in evaluated.items()
            for i, (c, q) in enumerate(zip(view.conditions, qs))
            if view.passes(q)
        )

    run([d for d in view.designs if all(i % stride == 0 for i in index[d])])
    if view.mode == "PB-INV":
        seeds = [d for _, d in feasible_designs()[:top_k]]
    else:
        seeds = []
        for _, d, _, _ in feasible_points():
            if d not in seeds:
                seeds.append(d)
            if len(seeds) == top_k:
                break
    run(
        [
            d
            for d in view.designs
            if any(
                all(abs(a - b) <= radius for a, b in zip(index[d], index[s]))
                for s in seeds
            )
        ]
    )
    if view.mode == "PB-INV":
        ranked = feasible_designs()
        return [] if not ranked else [view.select_design(ranked[0][1], ranked[0][0])]
    return [
        view.select_point(d, c, evaluated[d][i])
        for _, d, c, i in feasible_points()[: view.verification_budget]
    ]


@dataclass(frozen=True)
class Method:
    run: Callable
    modes: tuple
    #: parameter -> (low, high), inclusive integers. `screen_condition` is
    #: bounded by the request's conditions when it runs.
    parameters: dict
    summary: str


#: The registered methods a proposal may name. The fixed baseline is each
#: Challenge's own and is not proposable.
METHODS = {
    "screen_then_confirm": Method(
        run=screen_then_confirm,
        modes=("PB-INV",),
        parameters={"screen_condition": (0, None)},
        summary=(
            "screen every design at one condition, then confirm the screened-"
            "feasible designs at the others, lowest screened objective first"
        ),
    ),
    "coarse_to_fine": Method(
        run=coarse_to_fine,
        modes=("PB-INV", "PB-ADV"),
        parameters={"stride": (2, 8), "radius": (1, 4), "top_k": (1, 16)},
        summary=(
            "query a strided subgrid at every condition, then the neighbourhood "
            "of the best results, and select from everything queried"
        ),
    ),
}


def registry():
    """The methods as data, for a brief."""
    return {
        name: {
            "modes": list(m.modes),
            "parameters": {k: list(v) for k, v in m.parameters.items()},
            "summary": m.summary,
        }
        for name, m in sorted(METHODS.items())
    }


def check(method, parameters, *, mode, conditions):
    """A proposed method and its parameters, checked; returns the method."""
    if method not in METHODS:
        raise MethodError("method_not_registered", str(method))
    spec = METHODS[method]
    if mode not in spec.modes:
        raise MethodError("method_does_not_serve_this_mode", f"{method} {mode}")
    if type(parameters) is not dict or set(parameters) != set(spec.parameters):
        raise MethodError("parameters_not_exactly_the_methods", method)
    for name, (low, high) in spec.parameters.items():
        value = parameters[name]
        high = conditions - 1 if high is None else high
        if type(value) is not int or not low <= value <= high:
            raise MethodError("parameter_outside_bounds", name)
    return spec


def run(method, parameters, view, oracle):
    spec = check(method, parameters, mode=view.mode, conditions=len(view.conditions))
    return spec.run(view, oracle, **parameters)
