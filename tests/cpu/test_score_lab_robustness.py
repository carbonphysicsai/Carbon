"""Toy-only negative controls for robustness as score, gate or abstention."""

import copy
import json
import statistics
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_robustness, components, physics
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "scripts/dev/score_lab/physics-shape-example.json"


def _inputs():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    config["decision"]["abstention_loss"] = 0.4
    config["decision"]["uncertainty_abstention_threshold"] = 0.08
    search = {
        "seed": 9,
        "random_draws": 3,
        "hill_epochs": 1,
        "base_member_id": "physics-understanding-0",
        "value_scope": "in_range",
        "parameters": {
            "robustness": [0.0, 0.2, 0.05],
            "sigma_scale": [0.2, 8.0, 2.0],
        },
    }
    levers = {
        "schema": campaign_robustness.SCHEMA,
        "robustness_scale": 0.08,
        "blend_weights": [0.5],
        "gate_limits": [0.03, 0.1],
        "honest_abstention": {
            "weight": 0.5,
            "error_limit": 0.05,
            "sigma_scale": 0.05,
            "decline_threshold": 0.08,
            "outside_weight": 0.5,
        },
    }
    return config, search, levers


def _rule(predictions, references, metadata):
    assert set(predictions) == set(references)
    assert all(qid.startswith("S-") for qid in references)
    assert "value_questions" not in metadata and "value_losses" not in metadata
    assert all(
        all(qid.startswith("N-S-") for qid in row["references"])
        for row in metadata["neighbours"]
    )
    error = statistics.fmean(
        abs(predictions[qid][aid]["objective"] - ref["objective"])
        for qid, actions in references.items()
        for aid, ref in actions.items()
    )
    result = {"score": 1 - error, "gate": "PASS"}
    switch = metadata["knobs"]["physics"]
    robustness = metadata["physics"]["robustness"]
    if switch["mode"] == "GATE" and robustness > switch["limit"]["robustness"]:
        result["gate"] = "FAIL"
    if switch["mode"] == "BLEND":
        result["score"] /= (
            1
            + switch["weight"]["robustness"]
            * robustness
            / switch["limit"]["robustness"]
        )
    return result


def test_fixed_slate_budget_scope_and_gate_curve():
    config, search, levers = _inputs()
    report = campaign_robustness.run(
        config,
        "toy",
        {"rule": _rule},
        candidates_sha256="toy",
        search=search,
        lever=levers,
    )
    assert report == campaign_robustness.run(
        config,
        "toy",
        {"rule": _rule},
        candidates_sha256="toy",
        search=search,
        lever=levers,
    )
    assert [row["arm"] for row in report["arms"]] == [
        "baseline",
        "term:0.5",
        "gate:0.03",
        "gate:0.1",
        "honest_abstention",
    ]
    assert {row["score_queries"] for row in report["arms"]} == {
        report["proposal_count"]
    }
    assert {row["value_queries"] for row in report["arms"]} == {
        report["proposal_count"] * len(campaign_robustness.SCOPES)
    }
    strict, loose = report["arms"][2:4]
    assert strict["admitted_proposals"] < loose["admitted_proposals"]
    for row in report["arms"]:
        assert set(row["scopes"]) == set(campaign_robustness.SCOPES)
        for scope in row["scopes"].values():
            if scope["sampled_goodhart_gap"] is not None:
                assert scope["sampled_goodhart_gap"] >= 0
    assert all(
        scope["contrast"] == "NO_OBSERVED_DIFFERENCE_ON_SLATE"
        for scope in report["arms"][0]["scopes"].values()
    )
    assert strict["scopes"]["in_range"]["contrast"] in {
        "BETTER_ON_SLATE",
        "WORSE_ON_SLATE",
        "NO_OBSERVED_DIFFERENCE_ON_SLATE",
    }


def test_honest_uncertainty_rewards_warning_and_penalises_overwarning():
    _, _, levers = _inputs()
    spec = levers["honest_abstention"]

    def constant(_predictions, _references, _metadata):
        return {"score": 0.0, "gate": "PASS"}

    wrapped = components.with_honest_abstention(constant, spec=spec)
    good = {"q": {"a": {"objective": 1.0, "margins": {"m": 0.1}, "sigma": 0.001}}}
    warned = copy.deepcopy(good)
    warned["q"]["a"]["sigma"] = 1.0
    ref = {"q": {"a": {"status": "FEASIBLE", "objective": 1.0}}}
    outside_ref = {"n": {"a": {"status": "INFEASIBLE", "objective": 2.0}}}
    outside_confident = {
        "n": {"a": {"objective": 1.0, "margins": {"m": 0.1}, "sigma": 0.001}}
    }
    outside_warned = copy.deepcopy(outside_confident)
    outside_warned["n"]["a"]["sigma"] = 1.0
    metadata = {
        "neighbours": [{"predictions": outside_confident, "references": outside_ref}]
    }
    assert (
        wrapped(good, ref, metadata)["score"] > wrapped(warned, ref, metadata)["score"]
    )
    metadata["neighbours"][0]["predictions"] = outside_warned
    assert (
        wrapped(good, ref, metadata)["score"]
        > wrapped(
            good,
            ref,
            {
                "neighbours": [
                    {"predictions": outside_confident, "references": outside_ref}
                ]
            },
        )["score"]
    )
    detail = wrapped(good, ref, metadata)["detail"]["toy_honesty"]
    assert detail["correct_declines"] == 1 and detail["over_declines"] == 0
    with pytest.raises(LabRefused, match="component_abstention_spec"):
        components.with_honest_abstention(constant, spec={**spec, "sigma_scale": 0})


def test_high_uncertainty_declines_useful_toy_action_and_costs_value():
    question = {
        "fallback": "f",
        "actions": {
            "f": {"status": "FEASIBLE", "objective": 1.0},
            "a": {"status": "FEASIBLE", "objective": 0.0},
        },
    }
    decision = {
        "k": 1,
        "unit": 1.0,
        "abstention_loss": 0.4,
        "unsafe_loss": 1.0,
        "uncertainty_abstention_threshold": 0.08,
    }
    confident = {"a": {"objective": 0.0, "feasible": True, "sigma": 0.001}}
    overcautious = {"a": {"objective": 0.0, "feasible": True, "sigma": 1.0}}
    assert physics._loss(question, confident, decision, 0.1) == -0.9
    assert physics._loss(question, overcautious, decision, 0.1) == 0.4


def test_missing_controlled_values_refuse():
    config, search, levers = _inputs()
    del config["decision"]["uncertainty_abstention_threshold"]
    with pytest.raises(LabRefused, match="robustness_value_decline_missing"):
        campaign_robustness.run(
            config,
            "toy",
            {"rule": _rule},
            candidates_sha256="toy",
            search=search,
            lever=levers,
        )
    config["decision"]["uncertainty_abstention_threshold"] = 0.08
    levers["gate_limits"] = []
    with pytest.raises(LabRefused, match="robustness_lever_spec"):
        campaign_robustness.run(
            config,
            "toy",
            {"rule": _rule},
            candidates_sha256="toy",
            search=search,
            lever=levers,
        )
    search["parameters"]["sigma_scale"] = [0.0, 8.0, 2.0]
    with pytest.raises(LabRefused, match="goodhart_trait_bounds"):
        campaign_robustness.run(
            config,
            "toy",
            {"rule": _rule},
            candidates_sha256="toy",
            search=search,
            lever={**levers, "gate_limits": [0.1]},
        )
