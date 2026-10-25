"""The owner's scoring sheet: the proof suite run over a grid of every OWNER constant (plan PROOF_RUN_SUNDAY_PLAN).

For one Challenge version this sweeps the query budget B, the honesty scale s_h, the A-leg tightening m, the
A_gen scale set and how A_gen enters A, over the models the proof suite names (the oracle, the good model, the
default, and the three gaming controls). Per grid point it reports, with no per-case value:

    good, default, headroom H = 1 - good, separation S = good - default, the controls' margin
    (good - the best control), whether the oracle reaches every reference and scores 1, and whether the row
    meets every stated condition (good at or below the target, S at least max(0.10, 5 x KOTH margin),
    every control below good, the oracle perfect).

The owner picks one row per Challenge. Nothing here chooses a constant, and nothing names a Challenge.

Cost: the model's answers at pool points never change, so the real models are cached (`pool_plugin.cached`)
and a grid point costs only the grader's own search, in pure Python. The A legs come from the sealed v2
grader on a bank once per model; an A-leg tightening m maps each leg by 1 / (1 + m (1/leg - 1)), the
Test Engineer's scale-curve rule (SCALE_OPTION_CURVES_20261024.md; an approximation until the registered U
gives the exact m), and the A_gen scales are explicit per-output sets the owner's sheet lists.
"""

from __future__ import annotations

import itertools
import json
import math
import statistics
from dataclasses import dataclass

from carbon.scoring import pool_grader
from carbon.scoring import pool_proof_suite as suite

#: The controls every row must beat. The in-distribution control is shown on every row; it is a pass criterion
#: only when `GridSpec.in_distribution_is_pass_criterion` (Phase 2: the extended targets).
CONTROLS = (
    "optimistic_near_limits",
    "wrong_near_the_optimum",
    "default_model",
    "floor",
)
REPORTED = ("in_distribution_only",)


@dataclass(frozen=True)
class GridSpec:
    in_distribution_is_pass_criterion: bool
    budgets: tuple
    honesty_scales: tuple
    honesty_reduction: str
    a_multipliers: tuple  # m for the A legs (1 = the registered scale)
    agen_scale_sets: tuple  # tuple of {output: scale}
    a_rules: tuple  # tuple of {"kind": "min"} | {"kind": "mean"} | {"kind": "weighted", "weight": w}
    c_rule: dict
    sigma0: float
    population: object  # None or an int
    good_target: float  # the good model's ceiling (0.75, OWNER-SCORE-GOOD-TARGET-01)
    koth_margin: float
    optimism_k: float
    wrong_radius: float
    wrong_k: float
    oracle_tolerance: float
    seed: int


def tighten(leg, m):
    """The scale-curve rule: a leg 1 / (1 + x) with its scale tightened by m becomes 1 / (1 + m x)."""
    if leg <= 0.0:
        return 0.0
    return 1.0 / (1.0 + m * (1.0 / leg - 1.0))


def descriptors(grid):
    """The models of the sheet, by name."""
    return {
        "oracle": {"kind": "oracle"},
        "good": {"kind": "good"},
        "default": {"kind": "default"},
        "optimistic_near_limits": {
            "kind": "noisy",
            "k": grid.optimism_k,
            "mode": "feasible_bias",
            "seed": grid.seed,
        },
        "in_distribution_only": {"kind": "in_distribution"},
        "wrong_near_the_optimum": {
            "kind": "wrong_near_optimum",
            "radius": grid.wrong_radius,
            "k": grid.wrong_k,
            "seed": grid.seed,
        },
        "default_model": {"kind": "default"},
        "floor": {"kind": "floor"},
    }


def run_grid(plugin, grid):
    """The owner sheet for one Challenge version: {"meta", "rows"}. Aggregates only."""
    if grid.honesty_reduction not in ("max", "rms"):
        raise pool_grader.PoolRefused("honesty_reduction_must_be_max_or_rms")
    all_specs = [spec for specs in plugin.sets for spec in specs]
    named = descriptors(grid)
    predictors = {
        name: suite.pool_predictor(plugin, d, all_specs) for name, d in named.items()
    }
    legs_by_model = {name: plugin.legs(d, plugin.sets[0]) for name, d in named.items()}
    rows = []
    d_cache = {}
    for budget, s_h in itertools.product(grid.budgets, grid.honesty_scales):
        optimizer = pool_grader.OptimizerPolicy(
            budget=budget, sigma0=grid.sigma0, population=grid.population
        )
        honesty = pool_grader.HonestyPolicy(scale=s_h, reduction=grid.honesty_reduction)
        for name in named:
            per_set = [
                pool_grader.grade_set(specs, predictors[name], optimizer, honesty)
                for specs in plugin.sets
            ]
            d_cache[(budget, s_h, name)] = (
                statistics.fmean(g.d for g in per_set),
                all(t.reached_reference for g in per_set for t in g.targets),
            )
    agen_cache = {}
    has_slice = any(spec.agen for specs in plugin.sets for spec in specs)
    for index, scales in enumerate(grid.agen_scale_sets):
        for name in named:
            values = (
                [
                    pool_grader.agen_accuracy(specs, predictors[name], scales)
                    for specs in plugin.sets
                ]
                if has_slice
                else []
            )
            values = [v for v in values if v is not None]
            agen_cache[(index, name)] = statistics.fmean(values) if values else None
    needed_gap = max(0.10, 5.0 * grid.koth_margin)
    for (budget, s_h), m, (agen_index, _), a_rule in itertools.product(
        itertools.product(grid.budgets, grid.honesty_scales),
        grid.a_multipliers,
        enumerate(grid.agen_scale_sets),
        grid.a_rules,
    ):
        totals = {}
        for name in named:
            legs = legs_by_model[name]
            a_legs = legs.get("A_legs")
            a = (
                statistics.fmean(tighten(v, m) for v in a_legs.values())
                if a_legs
                else tighten(legs["A"], m)
            )
            a_all = pool_grader.combine_a(a, agen_cache[(agen_index, name)], a_rule)
            d, _ = d_cache[(budget, s_h, name)]
            totals[name] = (
                0.0
                if legs.get("gates_ok") is False
                else pool_grader.total(a_all, d, legs["C"], grid.c_rule)
            )
        good, default = totals["good"], totals["default"]
        controls = {c: totals[c] for c in CONTROLS + REPORTED}
        judged = CONTROLS + (REPORTED if grid.in_distribution_is_pass_criterion else ())
        margin = good - max(totals[c] for c in judged)
        oracle_ok = d_cache[(budget, s_h, "oracle")][1] and math.isclose(
            totals["oracle"], 1.0, abs_tol=grid.oracle_tolerance
        )
        rows.append(
            {
                "B": budget,
                "s_h": s_h,
                "A_multiplier": m,
                "A_gen_scales": index_label(agen_index),
                "A_gen_rule": a_rule,
                "good": good,
                "default": default,
                "H": 1.0 - good,
                "S": good - default,
                "controls": controls,
                "controls_margin": margin,
                "oracle_reaches_all_references": d_cache[(budget, s_h, "oracle")][1],
                "oracle_total": totals["oracle"],
                "meets_all": bool(
                    good <= grid.good_target
                    and good - default >= needed_gap
                    and margin > 0.0
                    and oracle_ok
                ),
            }
        )
    meta = {
        "good_target": grid.good_target,
        "needed_separation": needed_gap,
        "koth_margin": grid.koth_margin,
        "controls": {
            "optimism_k": grid.optimism_k,
            "wrong_radius": grid.wrong_radius,
            "wrong_k": grid.wrong_k,
        },
        "agen_scale_sets": [dict(s) for s in grid.agen_scale_sets],
        "rows": len(rows),
        "rows_meeting_all": sum(r["meets_all"] for r in rows),
    }
    return {"meta": meta, "rows": rows}


def index_label(index):
    return f"set-{index}"


def sheet_markdown(title, result):
    """One owner sheet: the rows that meet every condition first, then the rest by the controls' margin."""
    meta, rows = result["meta"], result["rows"]
    order = sorted(
        rows,
        key=lambda r: (not r["meets_all"], -r["controls_margin"], r["B"], r["s_h"]),
    )
    lines = [
        f"# {title}: the owner's scoring sheet (aggregates only)",
        "",
        (
            f"Conditions: good at or below {meta['good_target']}; good minus default at least "
            f"{meta['needed_separation']:.3f} (max(0.10, 5 x KOTH margin {meta['koth_margin']})); every control "
            "below good; the oracle reaches every reference and scores 1."
        ),
        f"{meta['rows_meeting_all']} of {meta['rows']} grid points meet every condition. The owner picks one row.",
        "",
        "| meets | B | s_h | A mult | A_gen scales | A_gen rule | good | default | floor | H | S | controls margin | oracle ok |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in order:
        rule = r["A_gen_rule"]["kind"] + (
            f" {r['A_gen_rule']['weight']}"
            if r["A_gen_rule"]["kind"] == "weighted"
            else ""
        )
        lines.append(
            f"| {'YES' if r['meets_all'] else 'no'} | {r['B']} | {r['s_h']} | {r['A_multiplier']} | "
            f"{r['A_gen_scales']} | {rule} | {r['good']:.3f} | {r['default']:.3f} | {r['controls']['floor']:.3f} | {r['H']:.3f} | {r['S']:.3f} | "
            f"{r['controls_margin']:.3f} | {'yes' if r['oracle_reaches_all_references'] else 'NO'} |"
        )
    return "\n".join(lines) + "\n"


def dump(result):
    return json.dumps(result, indent=2, sort_keys=True)
