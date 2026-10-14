"""Equal-proposal toy Goodhart comparison of three robustness score levers.

All science values are explicit synthetic assumptions. The score callback sees
only score-side cells; buyer value is calculated after each fixed slate is
ranked. This module does not select or register a Carbon score rule.
"""

from __future__ import annotations

import copy
import math
import random

from . import campaign_goodhart, physics
from .core import LabRefused, canonical_sha

SCHEMA = "carbon.dev.score-lab-robustness-levers.v1"
SCOPES = ("in_range", "shifted", "extrapolated", "neighbourhood_blend")


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _slate(search):
    """Freeze all random and local proposals before looking at any score."""
    rng = random.Random(search["seed"])
    bounds = search["parameters"]
    names = sorted(bounds)
    rows, seen = [], set()

    def add(parameters):
        key = tuple(sorted(parameters.items()))
        if key not in seen:
            seen.add(key)
            rows.append(dict(parameters))

    for _ in range(search["random_draws"]):
        start = {
            name: (
                float(rng.randrange(2))
                if name == "score_path_only"
                else rng.uniform(bounds[name][0], bounds[name][1])
            )
            for name in names
        }
        add(start)
        for epoch in range(1, search["hill_epochs"] + 1):
            for name in names:
                low, high, step = bounds[name]
                for sign in (-1, 1):
                    row = dict(start)
                    row[name] = min(high, max(low, start[name] + sign * step * epoch))
                    add(row)
    if not rows or len(rows) > 2000:
        raise LabRefused("robustness_proposal_budget")
    return rows


def _validate(config, search, lever):
    campaign_goodhart.validate(config, search)
    if "physics_mode_index" in search:
        raise LabRefused("robustness_mode_owned_by_comparison")
    if "uncertainty_abstention_threshold" not in config["decision"]:
        raise LabRefused("robustness_value_decline_missing")
    if (
        not isinstance(lever, dict)
        or set(lever)
        != {
            "schema",
            "robustness_scale",
            "blend_weights",
            "gate_limits",
            "honest_abstention",
        }
        or lever["schema"] != SCHEMA
        or not _positive(lever["robustness_scale"])
        or not isinstance(lever["blend_weights"], list)
        or not lever["blend_weights"]
        or not all(_positive(value) for value in lever["blend_weights"])
        or len(set(lever["blend_weights"])) != len(lever["blend_weights"])
        or not isinstance(lever["gate_limits"], list)
        or not lever["gate_limits"]
        or not all(_positive(value) for value in lever["gate_limits"])
        or len(set(lever["gate_limits"])) != len(lever["gate_limits"])
    ):
        raise LabRefused("robustness_lever_spec")
    return lever


def run(config, candidate_id, spec, *, candidates_sha256, search, lever):
    """Score the same fixed slate in all arms, then inspect disjoint value."""
    _validate(config, search, lever)
    proposals = _slate(search)
    variant = copy.deepcopy(config)
    variant["physics_sweep"] = [{"mode": "OFF", "limit": {}, "weight": {}}]
    arms = [("baseline", 0, None)]
    for weight in lever["blend_weights"]:
        index = len(variant["physics_sweep"])
        variant["physics_sweep"].append(
            {
                "mode": "BLEND",
                "limit": {"robustness": lever["robustness_scale"]},
                "weight": {"robustness": weight},
            }
        )
        arms.append((f"term:{weight:g}", index, None))
    for limit in lever["gate_limits"]:
        index = len(variant["physics_sweep"])
        variant["physics_sweep"].append(
            {"mode": "GATE", "limit": {"robustness": limit}, "weight": {}}
        )
        arms.append((f"gate:{limit:g}", index, None))
    arms.append(
        ("honest_abstention", 0, {"honest_abstention": lever["honest_abstention"]})
    )
    physics.validate_config(variant)
    results = []
    for name, mode_index, component_spec in arms:
        arm_search = {**search, "physics_mode_index": mode_index}
        evaluator = campaign_goodhart.ToyTraitEvaluator(
            variant,
            candidate_id,
            spec,
            candidates_sha256=candidates_sha256,
            search=arm_search,
            component_spec=component_spec,
        )
        scores = [evaluator.score(row) for row in proposals]
        eligible = [i for i, score in enumerate(scores) if score is not None]
        winner = max(eligible, key=lambda i: (scores[i], -i)) if eligible else None
        value = {
            scope: [evaluator.value_loss(row, scope=scope) for row in proposals]
            for scope in SCOPES
        }
        scopes = {}
        for scope, losses in value.items():
            available = [loss for loss in losses if loss is not None]
            selected = losses[winner] if winner is not None else None
            best = min(available) if available else None
            scopes[scope] = {
                "score_winner_loss": selected,
                "slate_best_loss": best,
                "sampled_goodhart_gap": (
                    selected - best
                    if selected is not None and best is not None
                    else None
                ),
            }
        results.append(
            {
                "arm": name,
                "status": (
                    "MEASURED_SYNTHETIC_DEVELOPMENT"
                    if winner is not None
                    else "INSUFFICIENT_EVIDENCE"
                ),
                "physics_mode": variant["physics_sweep"][mode_index],
                "component_spec": component_spec,
                "score_queries": evaluator.calls["score"],
                "value_queries": evaluator.calls["value"],
                "admitted_proposals": len(eligible),
                "excluded_proposals": len(proposals) - len(eligible),
                "score_winner_parameters": (
                    proposals[winner] if winner is not None else None
                ),
                "scopes": scopes,
            }
        )
    baseline = results[0]["scopes"]
    for arm in results:
        for scope, row in arm["scopes"].items():
            old, new = baseline[scope]["score_winner_loss"], row["score_winner_loss"]
            delta = new - old if old is not None and new is not None else None
            row["loss_delta_vs_baseline"] = delta
            row["contrast"] = (
                "UNSCORED"
                if delta is None
                else (
                    "NO_OBSERVED_DIFFERENCE_ON_SLATE"
                    if delta == 0
                    else "BETTER_ON_SLATE" if delta < 0 else "WORSE_ON_SLATE"
                )
            )
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_DEVELOPMENT_DIAGNOSTIC",
        "candidate": candidate_id,
        "candidates_sha256": candidates_sha256,
        "config_sha256": canonical_sha(config),
        "search_sha256": canonical_sha(search),
        "lever_sha256": canonical_sha(lever),
        "proposal_count": len(proposals),
        "proposal_method": "SHARED_RANDOM_STARTS_AND_FIXED_COORDINATE_NEIGHBOURS",
        "value_oracle": "BEST_IN_SAME_FINITE_PROPOSAL_SLATE",
        "arms": results,
    }
