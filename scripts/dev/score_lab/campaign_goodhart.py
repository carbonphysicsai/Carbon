"""Toy random-plus-hill-climb Goodhart test on disjoint score/value tasks.

The score search sees only a candidate's score-side result. A separate oracle
search uses value losses solely to estimate the value attainable in this toy
parameter grammar. Neither search reads a Challenge bank or held-out material.
"""

from __future__ import annotations

import copy
import math
import random
import statistics

from . import candidates, physics
from .core import LabRefused, canonical_sha

TRAITS = frozenset(
    {
        "noise",
        "transfer",
        "law_rate",
        "law_size",
        "rollout_drift",
        "robustness",
        "extrapolation",
        "score_path_only",
    }
)
VALUE_SCOPES = frozenset({"in_range", "shifted", "extrapolated", "neighbourhood_blend"})


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(config, search):
    physics.validate_config(config)
    if (
        not isinstance(search, dict)
        or type(search.get("seed")) is not int
        or search["seed"] < 0
        or type(search.get("random_draws")) is not int
        or search["random_draws"] < 1
        or type(search.get("hill_epochs")) is not int
        or search["hill_epochs"] < 0
        or search.get("value_scope") not in VALUE_SCOPES
        or type(search.get("base_member_id")) is not str
        or not isinstance(search.get("parameters"), dict)
        or not search["parameters"]
        or set(search["parameters"]) - TRAITS
    ):
        raise LabRefused("goodhart_search_spec")
    members = [m for m in config["population"] if m["id"] == search["base_member_id"]]
    if len(members) != 1 or members[0]["kind"] != "MODEL":
        raise LabRefused("goodhart_base_member")
    for name, bounds in search["parameters"].items():
        if (
            not isinstance(bounds, list)
            or len(bounds) != 3
            or not all(_finite(value) for value in bounds)
            or not bounds[0] < bounds[1]
            or bounds[0] < 0
            or (name in {"transfer", "law_rate"} and bounds[1] > 1)
            or bounds[2] <= 0
            or (name == "score_path_only" and bounds != [0, 1, 1])
        ):
            raise LabRefused("goodhart_trait_bounds")
    return search


def _search(evaluate, search):
    rng = random.Random(search["seed"])
    bounds = search["parameters"]
    names = sorted(bounds)
    starts = [
        {
            name: (
                float(rng.randrange(2))
                if name == "score_path_only"
                else rng.uniform(bounds[name][0], bounds[name][1])
            )
            for name in names
        }
        for _ in range(search["random_draws"])
    ]
    scored = [(evaluate(p), p) for p in starts]
    available = [(rank, p) for rank, p in scored if rank is not None]
    if not available:
        return None
    best_rank, best = max(available, key=lambda row: row[0])
    best = dict(best)
    for _ in range(search["hill_epochs"]):
        changed = False
        for name in names:
            low, high, step = bounds[name]
            for direction in (-1, 1):
                proposal = dict(best)
                proposal[name] = min(high, max(low, best[name] + direction * step))
                rank = evaluate(proposal)
                if rank is not None and rank > best_rank:
                    best_rank, best = rank, proposal
                    changed = True
        if not changed:
            break
    return {"parameters": best, "rank": best_rank}


class ToyTraitEvaluator:
    """Keep the toy score callback separate from disjoint buyer-value tasks."""

    def __init__(
        self, config, candidate_id, spec, *, candidates_sha256, search, component_spec
    ):
        validate(config, search)
        if not callable(spec.get("rule")):
            raise LabRefused("goodhart_candidate_rule")
        self.config = config
        self.candidate_id = candidate_id
        self.spec = spec
        self.candidates_sha256 = candidates_sha256
        self.search = search
        self.component_spec = component_spec
        self.cache = {}
        self.calls = {"score": 0, "value": 0}

    def panel_for(self, parameters):
        key = tuple(sorted(parameters.items()))
        if key not in self.cache:
            variant = copy.deepcopy(self.config)
            member = next(
                m
                for m in variant["population"]
                if m["id"] == self.search["base_member_id"]
            )
            member.update(parameters)
            if "score_path_only" in parameters:
                member["score_path_only"] = bool(parameters["score_path_only"])
            self.cache[key] = physics.build(variant)
        return self.cache[key]

    def score(self, parameters, grain="aggregate"):
        self.calls["score"] += 1
        panel = self.panel_for(parameters)
        member = next(
            m for m in panel["members"] if m["id"] == self.search["base_member_id"]
        )
        questions = panel["score_questions"]
        if grain != "aggregate":
            if not grain.startswith("prefix:") or not grain[7:].isdigit():
                raise LabRefused("feedback_grain")
            count = int(grain[7:])
            if not 2 <= count <= len(questions):
                raise LabRefused("feedback_grain")
            questions = dict(list(questions.items())[:count])
        ids = set(questions)
        # The rule receives only the selected score-side questions and
        # matching toy neighbours. The held-out value side is never passed.
        score_panel = {
            "scope": "SYNTHETIC_DEVELOPMENT",
            "score_questions": questions,
            "members": [
                {
                    "id": m["id"],
                    "score_predictions": {
                        qid: prediction
                        for qid, prediction in m["score_predictions"].items()
                        if qid in ids
                    },
                }
                for m in panel["members"]
                if m["id"] == "control-bilinear"
            ],
        }
        rule = candidates.rule_from_spec(
            self.candidate_id,
            self.spec,
            path_digest=self.candidates_sha256,
            panel=score_panel,
            component_spec=self.component_spec,
        )
        metadata = {
            **member["score_metadata"],
            "knobs": {
                "physics": self.config["physics_sweep"][0],
                "neighbourhood_weight": self.config["neighbourhood"]["score_weight"],
            },
        }
        if grain != "aggregate":
            metadata["neighbours"] = [
                {
                    **neighbour,
                    "references": dict(list(neighbour["references"].items())[:count]),
                    "predictions": dict(list(neighbour["predictions"].items())[:count]),
                }
                for neighbour in metadata["neighbours"]
            ]
        result = rule(
            {qid: member["score_predictions"][qid] for qid in questions},
            questions,
            metadata,
        )
        if result is None or result["score"] is None or not result["admissible"]:
            return None
        if not _finite(result["score"]):
            raise LabRefused("goodhart_score_nonfinite")
        return (-result.get("tier", 0), result["score"])

    def value_loss(self, parameters):
        self.calls["value"] += 1
        panel = self.panel_for(parameters)
        view = physics.value_view(
            panel,
            self.search["value_scope"],
            self.config["neighbourhood"]["value_weight"],
        )
        member = next(
            m for m in view["members"] if m["id"] == self.search["base_member_id"]
        )
        losses = list(member["value_losses"].values())
        return (
            statistics.fmean(losses)
            if losses and all(x is not None for x in losses)
            else None
        )


def run(config, candidate_id, spec, *, candidates_sha256, search, component_spec=None):
    """Compare the score-optimising member with an independent value oracle."""
    experiment = ToyTraitEvaluator(
        config,
        candidate_id,
        spec,
        candidates_sha256=candidates_sha256,
        search=search,
        component_spec=component_spec,
    )
    score_best = _search(experiment.score, search)
    if score_best is None:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "all_score_proposals_unscored",
        }

    def oracle_rank(parameters):
        loss = experiment.value_loss(parameters)
        return (-loss,) if loss is not None else None

    oracle_best = _search(oracle_rank, search)
    score_value = experiment.value_loss(score_best["parameters"])
    oracle_value = (
        experiment.value_loss(oracle_best["parameters"]) if oracle_best else None
    )
    if score_value is None or oracle_value is None:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "value_unresolved"}
    return {
        "status": "MEASURED_SYNTHETIC_DEVELOPMENT",
        "config_sha256": canonical_sha(config),
        "search_sha256": canonical_sha(search),
        "candidates_sha256": candidates_sha256,
        "candidate": candidate_id,
        "value_scope": search["value_scope"],
        "oracle_kind": "RANDOM_PLUS_COORDINATE_HILLCLIMB_ON_ANALYTIC_TOY",
        "score_best_parameters": score_best["parameters"],
        "value_best_parameters": oracle_best["parameters"],
        "score_best_value_loss": score_value,
        "value_best_value_loss": oracle_value,
        "sampled_goodhart_gap": score_value - oracle_value,
        "calls": experiment.calls,
        "unique_toy_panels": len(experiment.cache),
    }
